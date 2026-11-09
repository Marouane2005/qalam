import pytest

from qalam.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://u:p@db.example.com/qalam?sslmode=require",
            "postgresql+psycopg://u:p@db.example.com/qalam?sslmode=require",
        ),
        ("postgres://u:p@db/qalam", "postgresql+psycopg://u:p@db/qalam"),
        ("postgresql+psycopg://u:p@db/qalam", "postgresql+psycopg://u:p@db/qalam"),
    ],
)
def test_database_url_uses_psycopg_driver(raw: str, expected: str) -> None:
    assert Settings(QALAM_DATABASE_URL=raw).database_url == expected


def test_database_url_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QALAM_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db/qalam")
    assert Settings().database_url == "postgresql+psycopg://u:p@db/qalam"
