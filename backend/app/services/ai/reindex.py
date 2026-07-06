"""Lazy vector reindexing from durable chunk storage.

On the free-tier deployment the Chroma index lives on ephemeral disk and is
wiped by every restart/redeploy, while accounts and document chunks live in
Postgres and survive. Before any retrieval, `ensure_indexed` rebuilds missing
vectors from the chunks table. Embeddings are computed locally
(all-MiniLM-L6-v2), so a rebuild costs CPU time only — no API spend.
"""

import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Document, DocumentChunk, DocumentStatus
from app.services.ai import vector_store

logger = logging.getLogger(__name__)


def ensure_indexed(user_id: int, document_id: int | None = None) -> None:
    """Rebuild vectors for the user's READY documents that are missing from Chroma.

    Scoped to one document when `document_id` is given, otherwise covers every
    READY document the user owns (the all-documents retrieval path). Never
    raises: retrieval should degrade to "no results" rather than 500 if the
    index can't be rebuilt.
    """
    try:
        with SessionLocal() as db:
            query = select(Document).where(
                Document.user_id == user_id, Document.status == DocumentStatus.READY
            )
            if document_id is not None:
                query = query.where(Document.id == document_id)

            for document in db.scalars(query):
                if vector_store.has_document(document.id):
                    continue
                chunks = db.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document.id)
                    .order_by(DocumentChunk.chunk_index)
                ).all()
                if not chunks:
                    logger.warning(
                        "Document %s has no stored chunks to reindex (pre-persistence upload?)",
                        document.id,
                    )
                    continue
                vector_store.add_document_chunks(
                    document_id=document.id,
                    user_id=document.user_id,
                    filename=document.filename,
                    chunks=[c.text for c in chunks],
                )
                logger.info(
                    "Reindexed document %s (%d chunks) from durable storage",
                    document.id,
                    len(chunks),
                )
    except Exception:  # noqa: BLE001 — degraded retrieval beats a crashed stream
        logger.exception("ensure_indexed failed for user %s", user_id)
