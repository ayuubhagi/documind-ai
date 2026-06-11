from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_documents: int
    ready_documents: int
    total_conversations: int
    questions_asked: int
    chunks_indexed: int


class ActivityPoint(BaseModel):
    date: str
    documents_uploaded: int
    questions_asked: int
