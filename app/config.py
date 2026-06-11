"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    Values are read (case-insensitively) from environment variables and an
    optional ``.env`` file. See ``.env.example`` for documentation.
    """

    # Devin API
    devin_api_key: str = ""
    devin_api_base: str = "https://api.devin.ai/v1"

    # GitHub (optional; only used by simulate.py to fetch real issues)
    github_token: str = ""

    # Remediation behaviour
    target_repo: str = "acrouch8090/superset"
    trigger_label: str = "devin-fix"
    default_base_branch: str = "master"

    # Storage + polling
    database_path: str = "data/remediation.db"
    poll_interval_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
