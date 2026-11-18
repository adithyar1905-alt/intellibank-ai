from typing import Annotated
from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_jwt
from app.models.auth import AuthToken
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_jwt(token)
        user_id = UUID(str(claims["sub"]))
        jti = str(claims["jti"])
        session_id = str(UUID(str(claims["sid"])))
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise unauthorized from None

    token_record = session.scalar(
        select(AuthToken).where(
            AuthToken.jti == jti,
            AuthToken.user_id == user_id,
            AuthToken.token_type == "access",
            AuthToken.session_id == session_id,
            AuthToken.revoked_at.is_(None),
            AuthToken.expires_at > datetime.now(timezone.utc),
        )
    )
    user = session.get(User, user_id)
    if token_record is None or user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]