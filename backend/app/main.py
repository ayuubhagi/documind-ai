import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — ensures all models are registered with Base
from app.api.routes import analytics, auth, conversations, documents
from app.core.config import settings
from app.core.database import Base, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    # Dev-friendly schema creation. For evolving production schemas, introduce
    # Alembic migrations (see README roadmap).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG-powered document intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["auth"])
app.include_router(documents.router, prefix=f"{settings.API_PREFIX}/documents", tags=["documents"])
app.include_router(
    conversations.router, prefix=f"{settings.API_PREFIX}/conversations", tags=["conversations"]
)
app.include_router(analytics.router, prefix=f"{settings.API_PREFIX}/analytics", tags=["analytics"])


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": settings.PROJECT_NAME}
