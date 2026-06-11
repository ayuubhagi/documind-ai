"""ChromaDB wrapper.

A single persistent collection holds every user's chunks; rows are scoped with
user_id / document_id metadata and every query filters on user_id, so one user
can never retrieve another user's content. Embeddings use Chroma's built-in
local model (all-MiniLM-L6-v2 via ONNX) — no per-token embedding cost and no
extra API dependency.
"""

from functools import lru_cache

import chromadb

from app.core.config import settings

_BATCH_SIZE = 100


@lru_cache
def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return client.get_or_create_collection(
        name="documents", metadata={"hnsw:space": "cosine"}
    )


def add_document_chunks(
    document_id: int, user_id: int, filename: str, chunks: list[str]
) -> None:
    collection = _get_collection()
    for start in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[start : start + _BATCH_SIZE]
        collection.add(
            ids=[f"{document_id}:{start + i}" for i in range(len(batch))],
            documents=batch,
            metadatas=[
                {
                    "document_id": document_id,
                    "user_id": user_id,
                    "filename": filename,
                    "chunk_index": start + i,
                }
                for i in range(len(batch))
            ],
        )


def search(
    user_id: int, query: str, top_k: int, document_id: int | None = None
) -> list[dict]:
    """Semantic search over the user's chunks, optionally scoped to one document."""
    collection = _get_collection()
    if document_id is None:
        where = {"user_id": user_id}
    else:
        where = {"$and": [{"user_id": user_id}, {"document_id": document_id}]}

    results = collection.query(query_texts=[query], n_results=top_k, where=where)

    hits: list[dict] = []
    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]
    for text, meta, distance in zip(documents[0], metadatas[0], distances[0]):
        hits.append(
            {
                "text": text,
                "document_id": meta["document_id"],
                "filename": meta["filename"],
                "chunk_index": meta["chunk_index"],
                "distance": distance,
            }
        )
    return hits


def delete_document(document_id: int) -> None:
    _get_collection().delete(where={"document_id": document_id})
