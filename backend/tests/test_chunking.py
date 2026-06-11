"""Unit tests for the chunking logic — pure functions, no app/DB needed."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from app.services.ai.document_processor import chunk_text  # noqa: E402


def test_short_text_single_chunk() -> None:
    chunks = chunk_text("Hello world.", chunk_size=1000, overlap=200)
    assert chunks == ["Hello world."]


def test_paragraphs_packed_up_to_chunk_size() -> None:
    paragraphs = [f"Paragraph number {i}." for i in range(20)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert all(len(c) <= 100 for c in chunks)
    # No content lost
    joined = " ".join(chunks)
    for p in paragraphs:
        assert p in joined


def test_oversized_paragraph_is_split_with_overlap() -> None:
    text = "x" * 2500
    chunks = chunk_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) >= 3
    assert all(len(c) <= 1000 for c in chunks)


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("", chunk_size=1000, overlap=200) == []
    assert chunk_text("\n\n  \n\n", chunk_size=1000, overlap=200) == []
