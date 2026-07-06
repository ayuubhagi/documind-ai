"""The pre-seeded sample document that lets visitors try DocuMind before
signing up. Owned by an internal system user so tenant isolation still holds;
the anonymous endpoint is the only reader."""

import logging
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Document, DocumentChunk, DocumentStatus, User
from app.services.ai import vector_store
from app.services.ai.document_processor import chunk_text

logger = logging.getLogger(__name__)

SYSTEM_EMAIL = "system@documind.internal"
SAMPLE_FILENAME = "sample-lease-agreement.txt"

SUGGESTED_QUESTIONS = [
    "What are the termination conditions in this lease?",
    "How much is rent, and what happens if I pay late?",
    "Am I allowed to have a pet?",
]

SAMPLE_TEXT = """RESIDENTIAL LEASE AGREEMENT (SAMPLE DOCUMENT)

1. PARTIES. This lease is between Northgate Properties LLC ("Landlord") and the undersigned tenant ("Tenant").

2. TERM. The lease term is twelve (12) months, beginning September 1, 2026 and ending August 31, 2027.

3. RENT. Monthly rent is $1,850, due on the first day of each month. A late fee of $50 applies to payments received after the fifth day of the month.

4. SECURITY DEPOSIT. Tenant shall pay a security deposit of $1,850 prior to move-in. The deposit will be returned within 30 days of move-out, less any deductions for damages beyond normal wear and tear.

5. TERMINATION. Either party may terminate this lease at the end of the term with sixty (60) days written notice. Early termination by the Tenant requires payment of two months rent as an early termination fee.

6. PETS. One cat or dog under 40 pounds is permitted with a one-time non-refundable pet fee of $300.

7. MAINTENANCE. Tenant must report maintenance issues within 48 hours of discovery. Landlord will address urgent repairs within 24 hours and routine repairs within 7 business days.

8. UTILITIES. Tenant is responsible for electricity, gas, and internet. Landlord covers water, sewer, and trash collection.
"""


def get_sample_document(db: Session) -> Document | None:
    user = db.scalar(select(User).where(User.email == SYSTEM_EMAIL))
    if user is None:
        return None
    return db.scalar(
        select(Document).where(Document.user_id == user.id, Document.filename == SAMPLE_FILENAME)
    )


def seed_sample_document(db: Session) -> None:
    """Idempotent startup seed. Failures are logged, never fatal — the app
    must still boot if e.g. the embedding model can't download yet."""
    try:
        if get_sample_document(db) is not None:
            return
        user = db.scalar(select(User).where(User.email == SYSTEM_EMAIL))
        if user is None:
            user = User(
                email=SYSTEM_EMAIL,
                full_name="DocuMind System",
                # Random password, never used for login.
                hashed_password=hash_password(secrets.token_hex(32)),
            )
            db.add(user)
            db.flush()

        chunks = chunk_text(SAMPLE_TEXT, chunk_size=1000, overlap=200)
        document = Document(
            user_id=user.id,
            filename=SAMPLE_FILENAME,
            file_path="",  # content lives in this module, not on disk
            mime_type="text/plain",
            file_size=len(SAMPLE_TEXT.encode()),
            status=DocumentStatus.READY,
            chunk_count=len(chunks),
        )
        db.add(document)
        db.flush()
        db.add_all(
            DocumentChunk(document_id=document.id, chunk_index=i, text=chunk)
            for i, chunk in enumerate(chunks)
        )
        db.flush()
        vector_store.add_document_chunks(
            document_id=document.id,
            user_id=user.id,
            filename=document.filename,
            chunks=chunks,
        )
        db.commit()
        logger.info("Seeded sample document (%d chunks)", len(chunks))
    except Exception:  # noqa: BLE001 — seeding must never block startup
        db.rollback()
        logger.exception("Failed to seed sample document; /api/sample will be unavailable")
