from sqlalchemy.orm import Session

from app.models import AnalyticsEvent


def track_event(
    db: Session, user_id: int, event_type: str, metadata: dict | None = None
) -> None:
    """Record an analytics event. Caller is responsible for committing."""
    db.add(AnalyticsEvent(user_id=user_id, event_type=event_type, event_metadata=metadata))
