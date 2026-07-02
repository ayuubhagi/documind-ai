import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models import Document, DocumentStatus, User
from app.schemas import DocumentOut
from app.services import analytics
from app.services.ai import vector_store
from app.services.ai.document_processor import SUPPORTED_EXTENSIONS, process_document

router = APIRouter()

# File signatures ("magic bytes") per extension. Extension checks alone are
# trivially bypassed by renaming; content sniffing catches that early with a
# clear error instead of a confusing processing failure later.
_MAGIC_BYTES = {
    ".pdf": (b"%PDF-",),
    ".docx": (b"PK\x03\x04",),  # docx is a zip container
}


def _content_matches_extension(suffix: str, contents: bytes) -> bool:
    signatures = _MAGIC_BYTES.get(suffix)
    if signatures is not None:
        return contents.startswith(signatures)
    # .txt / .md: no signature — require it to look like text (no NUL bytes).
    return b"\x00" not in contents[:8192]


def _get_owned_document(db: Session, user: User, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
def upload_document(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    contents = file.file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit",
        )
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
    if not _content_matches_extension(suffix, contents):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match its extension",
        )

    # Store under a UUID name so user-supplied filenames never touch the filesystem.
    user_dir = Path(settings.UPLOAD_DIR) / f"user_{current_user.id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_path = user_dir / f"{uuid.uuid4().hex}{suffix}"
    stored_path.write_bytes(contents)

    document = Document(
        user_id=current_user.id,
        filename=file.filename or stored_path.name,
        file_path=str(stored_path),
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(contents),
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    db.flush()
    analytics.track_event(
        db,
        current_user.id,
        "document_uploaded",
        {"document_id": document.id, "filename": document.filename, "size": len(contents)},
    )
    db.commit()
    db.refresh(document)

    # Index asynchronously — the request returns immediately with status=pending
    # and the frontend polls until the document is ready.
    background_tasks.add_task(process_document, document.id)

    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.user_id == current_user.id)
            .order_by(Document.created_at.desc())
        )
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    return _get_owned_document(db, current_user, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    document = _get_owned_document(db, current_user, document_id)

    vector_store.delete_document(document.id, user_id=current_user.id)
    Path(document.file_path).unlink(missing_ok=True)

    analytics.track_event(
        db, current_user.id, "document_deleted", {"document_id": document.id}
    )
    db.delete(document)
    db.commit()
