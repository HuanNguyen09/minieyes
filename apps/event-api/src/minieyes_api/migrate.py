"""Apply Alembic migrations programmatically (`python -m minieyes_api.migrate`)."""

import os
import sys

from alembic import command
from alembic.config import Config


def config(database_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "minieyes_api:migrations")
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(config(database_url), revision)


if __name__ == "__main__":
    url = os.environ.get("MINIEYES_DATABASE_URL")
    if not url:
        sys.exit("MINIEYES_DATABASE_URL is required")
    upgrade(url)
