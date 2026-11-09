import time
from pathlib import Path

from alembic import command
from alembic.config import Config

from qalam.logging import get_logger

log = get_logger("qalam.migrate")


def migrate(database_url: str) -> None:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def migrate_with_retry(database_url: str, attempts: int = 30) -> None:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            migrate(database_url)
            return
        except Exception as exc:
            last = exc
            log.warning("migration_waiting", attempt=attempt + 1, error=type(exc).__name__)
            time.sleep(1)
    raise RuntimeError(f"migration failed: {type(last).__name__ if last else 'unknown'}")
