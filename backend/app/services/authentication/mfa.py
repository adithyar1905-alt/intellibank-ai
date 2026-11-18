from datetime import datetime
import secrets

import pyotp

from app.core.security import decrypt_mfa_secret
from app.models.auth import UserMFA


def verify_and_consume_totp(
    mfa_settings: UserMFA, code: str, now: datetime | None = None
) -> bool:
    totp = pyotp.TOTP(decrypt_mfa_secret(mfa_settings.encrypted_secret))
    current_counter = totp.timecode(now or datetime.now().astimezone())
    matched_counter = next(
        (
            counter
            for counter in range(current_counter - 1, current_counter + 2)
            if counter > (mfa_settings.last_totp_counter or -1)
            and secrets.compare_digest(totp.at(counter * totp.interval), code)
        ),
        None,
    )
    if matched_counter is None:
        return False
    mfa_settings.last_totp_counter = matched_counter
    return True
