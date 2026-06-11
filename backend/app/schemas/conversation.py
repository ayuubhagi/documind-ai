from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    # None = conversation searches across all of the user's documents
    document_id: int | None = None
    title: str | None = Field(default=None, max_length=255)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int | None
    title: str
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: list | None
    created_at: datetime
