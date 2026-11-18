from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]


class RegistrationRequest(BaseModel):
    email: EmailStr
    password: Password
    phone_number: str | None = Field(default=None, min_length=7, max_length=32)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: SecretStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    token: SecretStr
    new_password: Password


class MessageResponse(BaseModel):
    message: str


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    phone_number: str | None
    is_active: bool
    is_verified: bool
    roles: list[str]
    permissions: list[str]


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAConfirmRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MFADisableRequest(BaseModel):
    password: SecretStr
    code: str = Field(pattern=r"^\d{6}$")


class MFAStatusResponse(BaseModel):
    enabled: bool
    verified_at: datetime | None