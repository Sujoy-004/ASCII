"""API configuration and environment variable loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ApiConfig:
    """Configuration settings for the FastAPI backend service."""

    environment: str = "development"
    cors_origins: list[str] = field(
        default_factory=lambda: [
            "https://rgb-ascii.pages.dev",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    cors_origin_regex: str = r"^https:\/\/[a-zA-Z0-9-]+\.rgb-ascii\.pages\.dev$"

    turnstile_secret_key: str = ""
    turnstile_site_key: str = ""
    turnstile_disabled: bool = False

    # Defensive resource limits per D-07
    max_chunk_bytes: int = 5 * 1024 * 1024  # 5 MB
    max_total_video_bytes: int = 35 * 1024 * 1024  # 35 MB
    max_total_gif_bytes: int = 20 * 1024 * 1024  # 20 MB
    max_video_duration: float = 60.0  # seconds
    max_gif_duration: float = 15.0  # seconds

    # Storage and quota limits per D-08
    storage_quota_bytes: int = 500 * 1024 * 1024  # 500 MB
    inactivity_timeout_seconds: int = 60
    encoding_timeout_seconds: int = 90
    max_job_lifetime_seconds: int = 600  # 10 minutes

    @classmethod
    def from_env(cls) -> ApiConfig:
        """Instantiate ApiConfig from environment variables."""
        env = os.environ.get("ENVIRONMENT", "development").lower()
        turnstile_disabled = os.environ.get("TURNSTILE_DISABLED", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        secret_key = os.environ.get("TURNSTILE_SECRET_KEY", "").strip()
        site_key = os.environ.get("TURNSTILE_SITE_KEY", "").strip()

        # Enforce mandatory Turnstile in production unless explicitly disabled per D-10
        if env == "production" and not turnstile_disabled:
            if not secret_key or not site_key:
                raise ValueError(
                    "Cloudflare Turnstile secret and site keys must be configured in "
                    "production unless TURNSTILE_DISABLED=true is explicitly set."
                )

        custom_origins = os.environ.get("CORS_ORIGINS")
        if custom_origins:
            origins = [o.strip() for o in custom_origins.split(",") if o.strip()]
        else:
            origins = [
                "https://rgb-ascii.pages.dev",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]

        return cls(
            environment=env,
            cors_origins=origins,
            turnstile_secret_key=secret_key,
            turnstile_site_key=site_key,
            turnstile_disabled=turnstile_disabled,
        )


# Global configuration instance
config = ApiConfig.from_env()
