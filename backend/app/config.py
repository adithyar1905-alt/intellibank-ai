from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str | None = None
    jwt_secret_key: str | None = None
    jwt_issuer: str = "intellibank-api"
    jwt_audience: str = "intellibank-clients"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    password_reset_minutes: int = 30
    mfa_encryption_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_ssl: bool = False
    password_reset_url: str = "http://localhost:3000/reset-password"
    kyc_encryption_key: str | None = None
    kyc_storage_path: Path = BACKEND_DIR / "private_uploads"
    fraud_model_path: Path | None = BACKEND_DIR / "private_models" / "fraud_model.joblib"
    fraud_large_amount_threshold: float = Field(default=10000.0, gt=0)
    fraud_hourly_count_threshold: int = Field(default=8, ge=1)
    fraud_alert_threshold: float = Field(default=0.35, ge=0, le=1)
    fraud_medium_threshold: float = Field(default=0.35, ge=0, le=1)
    fraud_review_threshold: float = Field(default=0.7, ge=0, le=1)
    fraud_critical_threshold: float = Field(default=0.9, ge=0, le=1)
    credit_model_path: Path | None = None
    ai_assistant_provider: str = "none"
    ai_assistant_api_url: str | None = None
    ai_assistant_api_key: str | None = None
    ai_assistant_model: str | None = None
    ai_assistant_timeout_seconds: int = Field(default=10, ge=1, le=30)

    @model_validator(mode="after")
    def validate_fraud_threshold_order(self) -> "Settings":
        if not (
            self.fraud_alert_threshold
            <= self.fraud_medium_threshold
            <= self.fraud_review_threshold
            <= self.fraud_critical_threshold
        ):
            raise ValueError("Fraud policy thresholds must be ordered from alert to critical.")
        return self

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()