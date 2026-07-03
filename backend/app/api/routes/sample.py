"""Anonymous try-before-signup endpoints for the seeded sample document.
Tightly IP-rate-limited: this is the only unauthenticated path that can reach
the LLM, so it gets the strictest budget in the app."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.schemas import MessageCreate
from app.services.ai.rag import answer_oneoff_stream
from app.services.sample import SUGGESTED_QUESTIONS, get_sample_document

router = APIRouter()


@router.get("")
def sample_info(db: Session = Depends(get_db)) -> dict:
    document = get_sample_document(db)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample document unavailable"
        )
    return {
        "filename": document.filename,
        "chunk_count": document.chunk_count,
        "suggested_questions": SUGGESTED_QUESTIONS,
    }


@router.post("/ask")
@limiter.limit("5/minute;15/day")
def ask_sample(
    request: Request,
    payload: MessageCreate,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    document = get_sample_document(db)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sample document unavailable"
        )
    return StreamingResponse(
        answer_oneoff_stream(document.user_id, document.id, payload.content),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
