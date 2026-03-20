from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRETS = {
    "dev-secret-change-me",
    "dev-webhook-secret",
    "dev-webhook-secret-change-in-production",
    "changeme",
    "secret",
    "password",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────
    app_env: Literal["development", "production", "test"] = "development"
    app_version: str = "2.0.0"
    app_secret_key: str = "dev-secret-change-me"

    # ── Database ─────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://uskill:uskill@localhost:5432/uskill"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    # Startup: number of retries before giving up waiting for Postgres
    database_connect_retries: int = 10
    database_connect_retry_delay: float = 2.0  # seconds between retries

    # ── Redis ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Rate limits (requests / minute per plan) ─────────────────────
    rate_limit_free: int = 10
    rate_limit_pro: int = 120
    rate_limit_enterprise: int = 2000

    # ── Skill / connection limits per plan ───────────────────────────
    max_episodes_free: int = 500
    max_episodes_pro: int = 10_000
    max_episodes_enterprise: int = 100_000
    max_connections_free: int = 3
    max_connections_pro: int = 25
    max_connections_enterprise: int = 0       # 0 = unlimited
    max_batch_size_free: int = 5
    max_batch_size_pro: int = 20
    max_batch_size_enterprise: int = 50

    # ── Rollback ─────────────────────────────────────────────────────
    rollback_ttl_hours: int = 72

    # ── Jobs ─────────────────────────────────────────────────────────
    job_retention_days: int = 7
    async_threshold_episodes: int = 2000

    # ── Webhooks ─────────────────────────────────────────────────────
    webhook_secret: str = "dev-webhook-secret"
    webhook_timeout_seconds: int = 10
    webhook_max_retries: int = 3
    # Max outbox delivery attempts before permanent failure
    webhook_outbox_max_attempts: int = 5

    # ── CORS — "*" or comma-separated origins ────────────────────────
    cors_origins: str = "*"

    # ── Scoring defaults ─────────────────────────────────────────────
    default_gap_threshold: float = 0.70
    default_blend_base: bool = True

    # ── Input sanitisation ───────────────────────────────────────────
    # Strip control chars, limit to printable + common unicode
    task_max_bytes: int = 8_000   # hard byte limit before bcrypt-style amplification
    task_allow_html: bool = False # reject <tags> in task strings (XSS defence-in-depth)

    # ── Observability ────────────────────────────────────────────────
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"  # OTLP gRPC
    otel_service_name: str = "uskill-api"

    # ── Derived helpers ───────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",")]

    def max_episodes_for_plan(self, plan: str) -> int:
        return {
            "free": self.max_episodes_free,
            "pro": self.max_episodes_pro,
            "enterprise": self.max_episodes_enterprise,
        }.get(plan, self.max_episodes_free)

    def max_connections_for_plan(self, plan: str) -> int:
        return {
            "free": self.max_connections_free,
            "pro": self.max_connections_pro,
            "enterprise": self.max_connections_enterprise,
        }.get(plan, self.max_connections_free)

    def max_batch_for_plan(self, plan: str) -> int:
        return {
            "free": self.max_batch_size_free,
            "pro": self.max_batch_size_pro,
            "enterprise": self.max_batch_size_enterprise,
        }.get(plan, self.max_batch_size_free)

    def rate_limit_for_plan(self, plan: str) -> int:
        return {
            "free": self.rate_limit_free,
            "pro": self.rate_limit_pro,
            "enterprise": self.rate_limit_enterprise,
        }.get(plan, self.rate_limit_free)

    # ── Validators ────────────────────────────────────────────────────
    @field_validator("default_gap_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.10 <= v <= 0.95:
            raise ValueError("gap_threshold must be between 0.10 and 0.95")
        return v

    @model_validator(mode="after")
    def enforce_production_secrets(self) -> "Settings":
        """Refuse to start in production with known-weak default secrets."""
        if self.app_env != "production":
            return self
        errors = []
        if self.app_secret_key in _WEAK_SECRETS or len(self.app_secret_key) < 32:
            errors.append(
                "APP_SECRET_KEY must be at least 32 chars and not a default value in production"
            )
        if self.webhook_secret in _WEAK_SECRETS or len(self.webhook_secret) < 20:
            errors.append(
                "WEBHOOK_SECRET must be at least 20 chars and not a default value in production"
            )
        if self.cors_origins == "*":
            errors.append(
                "CORS_ORIGINS must be set to explicit origins (not '*') in production"
            )
        if errors:
            raise ValueError(
                "Production security configuration errors:\n"
                + "\n".join(f"  • {e}" for e in errors)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
