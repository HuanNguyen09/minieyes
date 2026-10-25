"""Runtime configuration, read from MINIEYES_* environment variables."""

import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MINIEYES_")

    # MINIEYES_API_KEYS: JSON object site -> SHA-256 hex digest of that site's API key,
    # e.g. {"site-01": "9f86d081..."}. Only digests live in config and secrets.
    api_keys: dict[str, str] = {}
    database_url: str = "postgresql+psycopg://minieyes:minieyes@localhost:5432/minieyes"

    @field_validator("api_keys")
    @classmethod
    def _digests_only(cls, keys: dict[str, str]) -> dict[str, str]:
        for site, digest in keys.items():
            if not _SHA256_HEX.fullmatch(digest.lower()):
                raise ValueError(f"api key for {site!r} must be a SHA-256 hex digest")
        return {site: digest.lower() for site, digest in keys.items()}
