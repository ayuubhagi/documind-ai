"""Document ingestion pipeline: extract -> chunk -> embed -> index.

`process_document` runs as a FastAPI BackgroundTask after upload. It opens its
own DB session because the request-scoped session is closed by the time the
task executes.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Document, DocumentStatus
from app.services import analytics
from app.services.ai import vector_store

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def extract_text(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(file_path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        doc = DocxDocument(file_path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if suffix in {".txt", ".md"}:
        return Path(file_path).read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {suffix}")


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Paragraph-aware chunking with a sliding-window fallback.

    Paragraphs are packed into chunks up to `chunk_size` characters. Oversized
    paragraphs are hard-split with `overlap` characters of context carried into
    the next window, so sentences cut at a boundary still appear intact in one
    of the two chunks.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            flush()
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + chunk_size].strip())
                start += chunk_size - overlap
        elif len(current) + len(paragraph) + 2 > chunk_size:
            flush()
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph

    flush()
    return [c for c in chunks if c]


def process_document(document_id: int) -> None:
    """Background task entrypoint. Never raises — failures are written to the DB row."""
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            logger.warning("process_document: document %s not found", document_id)
            return

        document.status = DocumentStatus.PROCESSING
        db.commit()

        try:
            text = extract_text(document.file_path)
            if not text.strip():
                raise ValueError("No extractable text found in the document")

            chunks = chunk_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
            vector_store.add_document_chunks(
                document_id=document.id,
                user_id=document.user_id,
                filename=document.filename,
                chunks=chunks,
            )

            document.status = DocumentStatus.READY
            document.chunk_count = len(chunks)
            document.processed_at = datetime.now(UTC)
            document.error_message = None
            analytics.track_event(
                db,
                document.user_id,
                "document_processed",
                {"document_id": document.id, "chunks": len(chunks)},
            )
            db.commit()
            logger.info("Indexed document %s (%s chunks)", document.id, len(chunks))
        except Exception as exc:  # noqa: BLE001 — background task must not crash the worker
            logger.exception("Failed to process document %s", document_id)
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)[:2000]
            db.commit()
    finally:
        db.close()
