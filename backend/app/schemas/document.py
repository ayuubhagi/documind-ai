from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    mime_type: str
    file_size: int
    status: DocumentStatus
    error_message: str | None
    chunk_count: int
    created_at: datetime
    processed_at: datetime | None
