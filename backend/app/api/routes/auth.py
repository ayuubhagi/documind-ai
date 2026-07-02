from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas import LoginRequest, RefreshRequest, Token, UserCreate, UserOut
from app.services import analytics

router = APIRouter()


def _issue_tokens(db: Session, user: User) -> Token:
    """Create an access/refresh pair and record the refresh token server-side."""
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    payload = decode_token(refresh, "refresh")
    assert payload is not None  # we just created it
    db.add(
        RefreshToken(
            jti=payload["jti"],
            user_id=user.id,
            # PyJWT decodes `exp` as a unix timestamp.
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    )
    db.commit()
    return Token(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists"
        )

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    analytics.track_event(db, user.id, "user_registered")
    db.commit()
    db.refresh(user)

    return _issue_tokens(db, user)


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=Token)
@limiter.limit("30/minute")
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    """Exchange a valid refresh token for a new access/refresh pair (rotation).

    The presented token is revoked on use. If a token that was already rotated
    is presented again, that's a strong signal it was stolen, so every session
    for that user is revoked as a precaution.
    """
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
    )

    decoded = decode_token(payload.refresh_token, "refresh")
    if decoded is None:
        raise invalid

    record = db.scalar(select(RefreshToken).where(RefreshToken.jti == decoded["jti"]))
    if record is None:
        raise invalid
    if record.revoked:
        # Reuse of a rotated token: kill all of this user's refresh tokens.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == record.user_id)
            .values(revoked=True)
        )
        db.commit()
        raise invalid

    user = db.get(User, record.user_id)
    if user is None:
        raise invalid

    record.revoked = True
    db.commit()
    return _issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> None:
    """Revoke the presented refresh token so the session can't be extended."""
    decoded = decode_token(payload.refresh_token, "refresh")
    if decoded is None:
        return  # already invalid — nothing to revoke
    db.execute(
        update(RefreshToken).where(RefreshToken.jti == decoded["jti"]).values(revoked=True)
    )
    db.commit()


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
