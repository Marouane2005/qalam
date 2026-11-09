from pathlib import Path

from qalam.config import Settings

BOOTSTRAP_KEY = "qlm_test_bootstrap_key"


def make_settings(database_url: str, storage: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": database_url,
        "redis_url": "redis://localhost:6379/0",
        "storage_dir": str(storage),
        "samples_dir": str(Path(__file__).resolve().parents[2] / "samples"),
        "tasks_eager": True,
        "seed_demo": False,
        "embedding_backend": "hash",
        "bootstrap_email": "admin@example.com",
        "bootstrap_name": "Admin",
        "bootstrap_api_key": BOOTSTRAP_KEY,
        "bootstrap_workspace": "Library",
        "llm_chain": "mock",
        "rate_limit_per_minute": 1000,
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]
