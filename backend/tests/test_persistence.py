"""Durable-chunk persistence and lazy vector reindexing.

Simulates the production failure mode: Chroma's on-disk index is wiped by a
restart while the relational DB survives. Retrieval must transparently rebuild
the index from stored chunks.
"""

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["LLM_PROVIDER"] = "demo"
os.environ["EMBEDDING_PROVIDER"] = "hash"  # offline deterministic embeddings
os.environ["RATE_LIMIT_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Document, DocumentChunk  # noqa: E402
from app.services.ai import reindex, vector_store  # noqa: E402


def _register(client: TestClient) -> dict:
    payload = {
        "email": f"persist-{uuid.uuid4().hex[:10]}@example.com",
        "full_name": "Persistence Tester",
        "password": "supersecret123",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()


def _upload_ready_document(client: TestClient, headers: dict) -> int:
    response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("persistence-note.txt", b"The vault code is 7401.\n\nKeep it secret.", "text/plain")},
    )
    assert response.status_code in (200, 201), response.text
    document_id = response.json()["id"]
    detail = client.get(f"/api/documents/{document_id}", headers=headers).json()
    assert detail["status"] == "ready", detail
    return document_id


def test_chunks_persist_and_reindex_after_vector_loss() -> None:
    with TestClient(app) as client:
        auth = _register(client)
        headers = {"Authorization": f"Bearer {auth['access_token']}"}
        document_id = _upload_ready_document(client, headers)

        with SessionLocal() as db:
            document = db.get(Document, document_id)
            user_id = document.user_id
            stored = db.scalars(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            ).all()
        assert stored, "chunks must be written to the relational DB during processing"
        assert any("7401" in chunk.text for chunk in stored)
        assert vector_store.has_document(document_id)

        # Simulate an ephemeral-disk restart: vectors gone, DB intact.
        vector_store.delete_document(document_id, user_id=user_id)
        assert not vector_store.has_document(document_id)

        reindex.ensure_indexed(user_id, document_id)
        assert vector_store.has_document(document_id)
        hits = vector_store.search(user_id=user_id, query="vault code", top_k=3, document_id=document_id)
        assert hits and "7401" in hits[0]["text"]


def test_chunks_deleted_with_document() -> None:
    with TestClient(app) as client:
        auth = _register(client)
        headers = {"Authorization": f"Bearer {auth['access_token']}"}
        document_id = _upload_ready_document(client, headers)

        response = client.delete(f"/api/documents/{document_id}", headers=headers)
        assert response.status_code == 204

        with SessionLocal() as db:
            remaining = db.scalars(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            ).all()
        assert remaining == []
