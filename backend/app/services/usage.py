"""Server-side entitlement checks. These run inside the API request, against
the database, so free-tier limits hold no matter what the client does.

Limit responses use HTTP 402 with a machine-readable `code` so the frontend
can render an upgrade card instead of a generic error.
"""

from datetime import UTC, datetime, time

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Conversation, Document, Message, User

PAYMENT_REQUIRED = 402


def _upgrade_error(reason: str) -> HTTPException:
    return HTTPException(
        status_code=PAYMENT_REQUIRED,
        detail={"code": "upgrade_required", "reason": reason},
    )


def document_count(db: Session, user: User) -> int:
    return db.scalar(select(func.count(Document.id)).where(Document.user_id == user.id)) or 0


def questions_today(db: Session, user: User) -> int:
    midnight_utc = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    return (
        db.scalar(
            select(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user.id,
                Message.role == "user",
                Message.created_at >= midnight_utc,
            )
        )
        or 0
    )


def ensure_can_upload(db: Session, user: User) -> None:
    limit = settings.PRO_DOCUMENT_LIMIT if user.is_pro else settings.FREE_DOCUMENT_LIMIT
    if document_count(db, user) >= limit:
        if user.is_pro:
            raise HTTPException(
                status_code=400, detail=f"Document limit reached ({limit}). Delete one first."
            )
        raise _upgrade_error(
            f"The free plan includes {settings.FREE_DOCUMENT_LIMIT} document. "
            "Upgrade to Pro for up to 50."
        )


def ensure_can_ask(db: Session, user: User) -> None:
    if user.is_pro:
        return
    if questions_today(db, user) >= settings.FREE_QUESTIONS_PER_DAY:
        raise _upgrade_error(
            f"You've used your {settings.FREE_QUESTIONS_PER_DAY} free questions today. "
            "Pro is unlimited."
        )


def usage_summary(db: Session, user: User) -> dict:
    return {
        "plan": user.plan,
        "documents_used": document_count(db, user),
        "document_limit": (
            settings.PRO_DOCUMENT_LIMIT if user.is_pro else settings.FREE_DOCUMENT_LIMIT
        ),
        "questions_today": questions_today(db, user),
        "question_limit": None if user.is_pro else settings.FREE_QUESTIONS_PER_DAY,
    }
