from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentChunk(Base):
    """Extracted chunk text, persisted in the relational DB.

    The vector index (Chroma) lives on ephemeral disk in the free-tier
    deployment, so it can vanish on restart. Chunks stored here are the
    durable source of truth: embeddings are rebuilt from them on demand
    (see services/ai/reindex.py) at zero API cost — the embedding model
    is local.
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    document = relationship("Document", back_populates="chunks")
