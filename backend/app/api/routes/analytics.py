from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import AnalyticsEvent, Conversation, Document, DocumentStatus, Message, User
from app.schemas import ActivityPoint, OverviewStats

router = APIRouter()


@router.get("/overview", response_model=OverviewStats)
def overview(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> OverviewStats:
    total_documents = db.scalar(
        select(func.count(Document.id)).where(Document.user_id == current_user.id)
    )
    ready_documents = db.scalar(
        select(func.count(Document.id)).where(
            Document.user_id == current_user.id, Document.status == DocumentStatus.READY
        )
    )
    total_conversations = db.scalar(
        select(func.count(Conversation.id)).where(Conversation.user_id == current_user.id)
    )
    questions_asked = db.scalar(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == current_user.id, Message.role == "user")
    )
    chunks_indexed = db.scalar(
        select(func.coalesce(func.sum(Document.chunk_count), 0)).where(
            Document.user_id == current_user.id
        )
    )
    return OverviewStats(
        total_documents=total_documents or 0,
        ready_documents=ready_documents or 0,
        total_conversations=total_conversations or 0,
        questions_asked=questions_asked or 0,
        chunks_indexed=chunks_indexed or 0,
    )


@router.get("/activity", response_model=list[ActivityPoint])
def activity(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActivityPoint]:
    """Daily counts of uploads and questions over the last N days (zero-filled)."""
    since = datetime.now(UTC) - timedelta(days=days - 1)
    day_expr = func.date(AnalyticsEvent.created_at)

    rows = db.execute(
        select(day_expr.label("day"), AnalyticsEvent.event_type, func.count())
        .where(
            AnalyticsEvent.user_id == current_user.id,
            AnalyticsEvent.created_at >= since,
            AnalyticsEvent.event_type.in_(["document_uploaded", "question_asked"]),
        )
        .group_by(day_expr, AnalyticsEvent.event_type)
    ).all()

    # func.date returns a date on Postgres and a string on SQLite — normalise to ISO strings.
    counts: dict[str, dict[str, int]] = {}
    for day, event_type, count in rows:
        key = day.isoformat() if isinstance(day, date) else str(day)
        counts.setdefault(key, {})[event_type] = count

    points: list[ActivityPoint] = []
    today = datetime.now(UTC).date()
    for offset in range(days - 1, -1, -1):
        key = (today - timedelta(days=offset)).isoformat()
        day_counts = counts.get(key, {})
        points.append(
            ActivityPoint(
                date=key,
                documents_uploaded=day_counts.get("document_uploaded", 0),
                questions_asked=day_counts.get("question_asked", 0),
            )
        )
    return points
