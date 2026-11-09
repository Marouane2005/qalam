import pytest

from qalam.config import Settings
from qalam.main import create_app
from qalam.services.ingest import safe_filename, sniff


def test_openapi_lists_the_reading_routes() -> None:
    app = create_app(
        Settings(
            database_url="postgresql+psycopg://qalam:qalam@localhost/qalam",
            llm_chain="mock",
            bootstrap_api_key="",
            log_level="WARNING",
        )
    )
    paths = app.openapi()["paths"]
    for path in (
        "/health",
        "/metrics",
        "/v1/me",
        "/v1/documents",
        "/v1/documents/{document_id}/summary",
        "/v1/documents/{document_id}/translations",
        "/v1/qa",
        "/v1/extract",
        "/v1/usage",
    ):
        assert path in paths
    assert app.title == "Qalam"


def test_blank_provider_overrides_are_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INCEPTION_TIMEOUT_S", "")
    monkeypatch.setenv("OPENROUTER_RETRIES", "")
    settings = Settings()
    assert settings.inception_timeout_s is None
    assert settings.openrouter_retries is None


def test_filename_and_sniff() -> None:
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("ملاحظة.txt").endswith(".txt")
    assert sniff(b"%PDF-1.7", ".pdf")
    assert not sniff(b"hello", ".pdf")
    assert sniff("مرحبا".encode("cp1256"), ".txt")
    assert sniff(b"\x89PNG\r\n", ".png")
