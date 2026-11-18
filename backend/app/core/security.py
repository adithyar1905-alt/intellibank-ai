from datetime import datetime, timezone
import hashlib
import secrets
import uuid

import jwt
from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash

from app.config import get_settings


password_hasher = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def _jwt_secret() -> str:
    secret = get_settings().jwt_secret_key
    if secret is None or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 bytes.")
    return secret


def create_access_jwt(
    user_id: uuid.UUID,
    jti: str,
    session_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "sid": session_id,
        "type": "access",
        "iat": issued_at,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_jwt(token: str) -> dict[str, object]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        _jwt_secret(),
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={
            "require": ["sub", "jti", "sid", "type", "iat", "exp", "iss", "aud"]
        },
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Unexpected token type.")
    return payload


def encrypt_mfa_secret(secret: str) -> str:
    key = get_settings().mfa_encryption_key
    if key is None:
        raise RuntimeError("MFA_ENCRYPTION_KEY must be configured to enable MFA.")
    try:
        fernet = Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("MFA_ENCRYPTION_KEY is not a valid Fernet key.") from exc
    return fernet.encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_mfa_secret(encrypted_secret: str) -> str:
    key = get_settings().mfa_encryption_key
    if key is None:
        raise RuntimeError("MFA_ENCRYPTION_KEY must be configured to use MFA.")
    try:
        return Fernet(key.encode("ascii")).decrypt(
            encrypted_secret.encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("Unable to decrypt the stored MFA secret.") from exc


def new_token_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)