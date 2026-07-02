import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import models  # noqa: F401 — ensures all models are registered with Base
from app.api.routes import analytics, auth, conversations, documents
from app.core.config import DEV_SECRET_KEY, settings
from app.core.database import Base, SessionLocal, engine
from app.core.rate_limit import limiter
from app.models import Document, DocumentStatus
from app.services.ai.llm import validate_provider_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _check_secret_key() -> None:
    """Refuse to run in production with the public dev signing key.

    The dev fallback key is committed to the repo, so any deployment using it
    has forgeable JWTs. Failing at startup turns a silent security hole into
    an obvious configuration error.
    """
    if settings.SECRET_KEY != DEV_SECRET_KEY:
        return
    if settings.is_production:
        raise RuntimeError(
            "SECRET_KEY is still the public development default. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    logger.warning(
        "SECRET_KEY is the public development default — fine locally, never in production."
    )


def _fail_stale_processing_documents() -> None:
    """Mark documents stuck in pending/processing as failed.

    Document indexing runs as an in-process BackgroundTask; if the server
    restarts mid-job, the task dies and the row would otherwise sit in
    'pending' forever with the frontend polling it indefinitely.
    """
    with SessionLocal() as db:
        stale = (
            db.query(Document)
            .filter(Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING]))
            .all()
        )
        for document in stale:
            document.status = DocumentStatus.FAILED
            document.error_message = (
                "Processing was interrupted by a server restart. Please upload the file again."
            )
        if stale:
            db.commit()
            logger.warning("Marked %d interrupted document(s) as failed on startup", len(stale))


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_secret_key()
    validate_provider_config()
    if settings.LLM_PROVIDER.lower() == "demo":
        logger.info("LLM_PROVIDER=demo — chat streams canned responses; no API calls, no cost.")

    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    if settings.DATABASE_URL.startswith("sqlite"):
        # SQLite is only used by the test suite; create the schema directly.
        # Postgres schemas are managed by Alembic (see Dockerfile / README).
        Base.metadata.create_all(bind=engine)
    _fail_stale_processing_documents()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG-powered document intelligence platform",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    return {"status": "ok", "service": settings.PROJECT_NAME, "llm_provider": settings.LLM_PROVIDER}
