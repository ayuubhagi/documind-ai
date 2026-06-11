from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Conversation, Document, DocumentStatus, Message, User
from app.schemas import ConversationCreate, ConversationOut, MessageCreate, MessageOut
from app.services import analytics
from app.services.ai.rag import answer_question_stream

router = APIRouter()


def _get_owned_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    if payload.document_id is not None:
        document = db.get(Document, payload.document_id)
        if document is None or document.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if document.status != DocumentStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is still being processed",
            )

    conversation = Conversation(
        user_id=current_user.id,
        document_id=payload.document_id,
        title=payload.title or "New conversation",
    )
    db.add(conversation)
    db.flush()
    analytics.track_event(
        db,
        current_user.id,
        "conversation_created",
        {"conversation_id": conversation.id, "document_id": payload.document_id},
    )
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .order_by(Conversation.created_at.desc())
        )
    )


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    return _get_owned_conversation(db, current_user, conversation_id)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Message]:
    conversation = _get_owned_conversation(db, current_user, conversation_id)
    return conversation.messages


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Ask a question and stream the grounded answer back as Server-Sent Events."""
    conversation = _get_owned_conversation(db, current_user, conversation_id)
    return StreamingResponse(
        answer_question_stream(db, current_user, conversation, payload.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Tell nginx not to buffer the stream in production.
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    conversation = _get_owned_conversation(db, current_user, conversation_id)
    db.delete(conversation)
    db.commit()
