from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

import jwt
import pyotp
from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authentication import CurrentUser, oauth2_scheme
from app.core.permissions import require_roles
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    decode_access_jwt,
    encrypt_mfa_secret,
    hash_opaque_token,
    hash_password,
    utc_now,
    verify_password,
)
from app.database import get_db
from app.integrations.email.password_reset import (
    password_reset_email_is_configured,
    send_password_reset_email,
)
from app.models.auth import AuthToken, UserMFA
from app.models.user import Role, User
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    MFAConfirmRequest,
    MFADisableRequest,
    MFASetupResponse,
    MFAStatusResponse,
    MessageResponse,
    PasswordResetRequest,
    RegistrationRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services.authentication.mfa import verify_and_consume_totp
from app.services.authentication.tokens import (
    issue_password_reset_token,
    issue_token_pair,
    revoke_all_tokens,
)


router = APIRouter(prefix="/auth", tags=["authentication"])
DatabaseSession = Annotated[Session, Depends(get_db)]
ResetEmailSender = Callable[[str, str], None]


def get_password_reset_sender() -> ResetEmailSender:
    if not password_reset_email_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email delivery is not configured.",
        )
    return send_password_reset_email


def _set_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a customer account",
)
def register(
    payload: RegistrationRequest, session: DatabaseSession, response: Response
) -> TokenResponse:
    _set_no_store(response)
    email = str(payload.email).lower()
    existing = session.scalar(
        select(User.id).where(
            (User.email == email)
            | (
                User.phone_number == payload.phone_number
                if payload.phone_number
                else False
            )
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email or phone number is already registered.")

    customer_role = session.scalar(select(Role).where(Role.name == "Customer"))
    if customer_role is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Default roles are not provisioned. Apply database migrations.",
        )

    user = User(
        email=email,
        phone_number=payload.phone_number,
        password_hash=hash_password(payload.password.get_secret_value()),
        roles=[customer_role],
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="Email or phone number is already registered."
        ) from None

    tokens = issue_token_pair(session, user)
    session.commit()
    return tokens


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and obtain access and refresh tokens",
)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: DatabaseSession,
    response: Response,
    mfa_code: Annotated[
        str | None,
        Form(
            pattern=r"^\d{6}$",
            description="Required when TOTP multi-factor authentication is enabled.",
        ),
    ] = None,
) -> TokenResponse:
    user = session.scalar(
        select(User).where(User.email == form.username.strip().lower())
    )
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    valid_password = verify_password(form.password, password_hash)
    if user is None or not user.is_active or not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    mfa = session.scalar(
        select(UserMFA).where(UserMFA.user_id == user.id).with_for_update()
    )
    if mfa is not None and mfa.enabled:
        try:
            valid_mfa = (
                mfa_code is not None and verify_and_consume_totp(mfa, mfa_code)
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not valid_mfa:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid multi-factor authentication code is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    _set_no_store(response)
    user.last_login_at = utc_now()
    tokens = issue_token_pair(session, user)
    session.commit()
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate a refresh token",
)
def refresh_tokens(
    payload: RefreshRequest, session: DatabaseSession, response: Response
) -> TokenResponse:
    _set_no_store(response)
    now = utc_now()
    old_token = session.scalar(
        select(AuthToken)
        .where(
            AuthToken.token_hash
            == hash_opaque_token(payload.refresh_token.get_secret_value()),
            AuthToken.token_type == "refresh",
            AuthToken.revoked_at.is_(None),
            AuthToken.consumed_at.is_(None),
            AuthToken.expires_at > now,
        )
        .with_for_update()
    )
    if old_token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    user = session.get(User, old_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    old_token.consumed_at = now
    tokens = issue_token_pair(session, user, old_token.session_id)
    session.commit()
    return tokens


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke the current access and refresh token session",
)
def logout(
    session: DatabaseSession,
    user: CurrentUser,
    access_token: Annotated[str, Depends(oauth2_scheme)],
) -> MessageResponse:
    try:
        claims = decode_access_jwt(access_token)
        session_id = str(claims["sid"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from None

    session.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user.id,
            AuthToken.session_id == session_id,
            AuthToken.revoked_at.is_(None),
        )
        .values(revoked_at=utc_now())
    )
    session.commit()
    return MessageResponse(message="Logged out.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password-reset email",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    session: DatabaseSession,
    send_email: Annotated[ResetEmailSender, Depends(get_password_reset_sender)],
) -> MessageResponse:
    user = session.scalar(
        select(User).where(User.email == str(payload.email).lower())
    )
    if user is not None and user.is_active:
        token = issue_password_reset_token(session, user)
        session.flush()
        send_email(user.email, token)
        session.commit()
    return MessageResponse(
        message="If the account exists, password reset instructions will be sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset a password using a one-time reset token",
)
def reset_password(
    payload: PasswordResetRequest, session: DatabaseSession
) -> MessageResponse:
    now = utc_now()
    reset_token = session.scalar(
        select(AuthToken)
        .where(
            AuthToken.token_hash
            == hash_opaque_token(payload.token.get_secret_value()),
            AuthToken.token_type == "password_reset",
            AuthToken.revoked_at.is_(None),
            AuthToken.consumed_at.is_(None),
            AuthToken.expires_at > now,
        )
        .with_for_update()
    )
    if reset_token is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user = session.get(User, reset_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user.password_hash = hash_password(payload.new_password.get_secret_value())
    reset_token.consumed_at = now
    revoke_all_tokens(session, user.id)
    session.commit()
    return MessageResponse(message="Password has been reset.")


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get the authenticated user's profile and granted permissions",
)
def get_me(user: CurrentUser) -> CurrentUserResponse:
    permissions = {
        f"{permission.resource}:{permission.action}"
        for role in user.roles
        for permission in role.permissions
    }
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        phone_number=user.phone_number,
        is_active=user.is_active,
        is_verified=user.is_verified,
        roles=[role.name for role in user.roles],
        permissions=sorted(permissions),
    )


@router.get(
    "/roles",
    response_model=list[str],
    summary="List roles (bank administrator only)",
)
def list_roles(
    user: Annotated[User, Depends(require_roles("Super Admin", "Bank Admin"))],
    session: DatabaseSession,
) -> list[str]:
    del user
    return list(session.scalars(select(Role.name).order_by(Role.name)))


@router.get(
    "/mfa/status",
    response_model=MFAStatusResponse,
    summary="Get the current user's multi-factor authentication status",
)
def mfa_status(user: CurrentUser) -> MFAStatusResponse:
    mfa = user.mfa_settings
    return MFAStatusResponse(
        enabled=bool(mfa and mfa.enabled),
        verified_at=mfa.verified_at if mfa else None,
    )


@router.post(
    "/mfa/setup",
    response_model=MFASetupResponse,
    summary="Create a TOTP authenticator setup for the current user",
)
def setup_mfa(
    user: CurrentUser, session: DatabaseSession, response: Response
) -> MFASetupResponse:
    _set_no_store(response)
    existing = session.scalar(
        select(UserMFA).where(UserMFA.user_id == user.id).with_for_update()
    )
    if existing is not None and existing.enabled:
        raise HTTPException(status_code=409, detail="Multi-factor authentication is enabled.")

    secret = pyotp.random_base32()
    try:
        encrypted = encrypt_mfa_secret(secret)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if existing is None:
        existing = UserMFA(user_id=user.id, encrypted_secret=encrypted)
        session.add(existing)
    else:
        existing.encrypted_secret = encrypted
        existing.verified_at = None
        existing.last_totp_counter = None
    session.commit()

    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="IntelliBank"
    )
    return MFASetupResponse(secret=secret, provisioning_uri=uri)


@router.post(
    "/mfa/confirm",
    response_model=MFAStatusResponse,
    summary="Confirm a TOTP authenticator code and enable MFA",
)
def confirm_mfa(
    payload: MFAConfirmRequest, user: CurrentUser, session: DatabaseSession
) -> MFAStatusResponse:
    mfa = session.scalar(
        select(UserMFA).where(UserMFA.user_id == user.id).with_for_update()
    )
    if mfa is None or mfa.enabled:
        raise HTTPException(status_code=409, detail="No pending MFA setup was found.")
    try:
        valid = verify_and_consume_totp(mfa, payload.code)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid authenticator code.")

    mfa.enabled = True
    mfa.verified_at = datetime.now(timezone.utc)
    session.commit()
    return MFAStatusResponse(enabled=True, verified_at=mfa.verified_at)


@router.post(
    "/mfa/disable",
    response_model=MFAStatusResponse,
    summary="Disable MFA after password and TOTP verification",
)
def disable_mfa(
    payload: MFADisableRequest, user: CurrentUser, session: DatabaseSession
) -> MFAStatusResponse:
    mfa = session.scalar(
        select(UserMFA).where(UserMFA.user_id == user.id).with_for_update()
    )
    if mfa is None or not mfa.enabled:
        raise HTTPException(status_code=409, detail="Multi-factor authentication is not enabled.")
    if not verify_password(payload.password.get_secret_value(), user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password.")
    try:
        valid = verify_and_consume_totp(mfa, payload.code)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid authenticator code.")

    session.delete(mfa)
    revoke_all_tokens(session, user.id)
    session.commit()
    return MFAStatusResponse(enabled=False, verified_at=None)