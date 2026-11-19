from __future__ import annotations

from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.config import get_settings


_SIGNATURES = (
    (b"%PDF-", ".pdf", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png"),
    (b"\xff\xd8\xff", ".jpg", "image/jpeg"),
)


def detect_document_type(content: bytes) -> tuple[str, str]:
    for signature, extension, media_type in _SIGNATURES:
        if content.startswith(signature):
            return extension, media_type
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Only PDF, PNG, and JPEG documents are supported.",
    )


def _fernet() -> Fernet:
    key = get_settings().kyc_encryption_key
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KYC document encryption is not configured.",
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KYC document encryption is not configured correctly.",
        ) from exc


def _storage_root() -> Path:
    path = get_settings().kyc_storage_path
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    return path.resolve()


def store_document(
    customer_id: UUID, document_id: UUID, content: bytes, extension: str
) -> str:
    relative_path = Path(str(customer_id)) / f"{document_id.hex}{extension}.enc"
    root = _storage_root()
    destination = root / relative_path
    encrypted_content = _fernet().encrypt(content)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encrypted_content)
    return relative_path.as_posix()


def load_document(reference: str) -> bytes:
    relative_path = Path(reference)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise RuntimeError("Stored KYC document reference is invalid.")
    root = _storage_root()
    source = (root / relative_path).resolve()
    if not source.is_relative_to(root):
        raise RuntimeError("Stored KYC document reference is invalid.")
    try:
        encrypted_content = source.read_bytes()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC document file is not available.",
        ) from exc
    try:
        return _fernet().decrypt(encrypted_content)
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt the stored KYC document.") from exc


def remove_document(reference: str) -> None:
    relative_path = Path(reference)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise RuntimeError("Stored KYC document reference is invalid.")
    root = _storage_root()
    source = (root / relative_path).resolve()
    if not source.is_relative_to(root):
        raise RuntimeError("Stored KYC document reference is invalid.")
    source.unlink(missing_ok=True)


def document_extension(reference: str) -> str:
    filename = Path(reference).name
    for suffix in (".pdf.enc", ".png.enc", ".jpg.enc"):
        if filename.endswith(suffix):
            return suffix.removesuffix(".enc")
    raise RuntimeError("Stored KYC document type is invalid.")


def document_media_type(extension: str) -> str:
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
    }[extension]
