from email.message import EmailMessage
from smtplib import SMTP, SMTP_SSL, SMTPException
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, status

from app.config import get_settings


def password_reset_email_is_configured() -> bool:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        return False
    parts = urlsplit(settings.password_reset_url)
    return bool(parts.netloc) and (
        parts.scheme == "https"
        or parts.hostname in {"localhost", "127.0.0.1", "::1"}
    )


def send_password_reset_email(email: str, token: str) -> None:
    settings = get_settings()
    if not password_reset_email_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email delivery is not configured.",
        )

    parts = urlsplit(settings.password_reset_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["token"] = token
    reset_link = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )

    message = EmailMessage()
    message["Subject"] = "IntelliBank password reset"
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message.set_content(
        "A password reset was requested for your IntelliBank account. "
        f"Use this link within {settings.password_reset_minutes} minutes:\n\n"
        f"{reset_link}\n\nIf you did not request this, you can ignore this email."
    )

    try:
        if settings.smtp_use_ssl:
            with SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                _send(smtp, settings.smtp_username, settings.smtp_password, message)
        else:
            with SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                _send(smtp, settings.smtp_username, settings.smtp_password, message)
    except (OSError, SMTPException) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email delivery failed.",
        ) from exc


def _send(
    smtp: SMTP | SMTP_SSL,
    username: str | None,
    password: str | None,
    message: EmailMessage,
) -> None:
    if username:
        smtp.login(username, password or "")
    smtp.send_message(message)
