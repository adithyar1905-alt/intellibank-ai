from datetime import timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import (
    create_access_jwt,
    generate_opaque_token,
    hash_opaque_token,
    new_token_id,
    utc_now,
)
from app.models.auth import AuthToken
from app.models.user import User
from app.schemas.auth import TokenResponse


def issue_token_pair(
    session: Session, user: User, session_id: str | None = None
) -> TokenResponse:
    now = utc_now()
    session_id = session_id or new_token_id()
    access_expiry = now + timedelta(minutes=get_settings().access_token_minutes)
    access_jti = new_token_id()
    access_token = create_access_jwt(
        user.id, access_jti, session_id, now, access_expiry
    )
    refresh_token = generate_opaque_token()
    refresh_expiry = now + timedelta(days=get_settings().refresh_token_days)

    session.add_all(
        [
            AuthToken(
                user_id=user.id,
                token_type="access",
                jti=access_jti,
                session_id=session_id,
                expires_at=access_expiry,
            ),
            AuthToken(
                user_id=user.id,
                token_type="refresh",
                token_hash=hash_opaque_token(refresh_token),
                session_id=session_id,
                expires_at=refresh_expiry,
            ),
        ]
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=get_settings().access_token_minutes * 60,
    )


def issue_password_reset_token(session: Session, user: User) -> str:
    settings = get_settings()
    token = generate_opaque_token()
    session.add(
        AuthToken(
            user_id=user.id,
            token_type="password_reset",
            token_hash=hash_opaque_token(token),
            expires_at=utc_now() + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    return token


def revoke_all_tokens(session: Session, user_id: uuid.UUID) -> None:
    now = utc_now()
    for token in session.scalars(
        select(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.revoked_at.is_(None),
        )
    ):
        token.revoked_at = now
