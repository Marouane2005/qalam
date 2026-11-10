from pathlib import Path

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient

from qalam.auth import GUEST_EMAIL_SUFFIX
from qalam.main import create_app
from tests.helpers import BOOTSTRAP_KEY, make_settings

pytestmark = pytest.mark.integration


def _guest_client(database_url: str, storage: Path, **overrides: object) -> TestClient:
    settings = make_settings(
        database_url,
        storage,
        guest_access=True,
        guest_signups_per_minute=1000,
        guest_daily_uploads=20,
        **overrides,
    )
    app = create_app(settings, redis_client=FakeRedis(decode_responses=True))
    return TestClient(app)


def test_guest_disabled_returns_404(client: TestClient) -> None:
    response = client.post("/v1/guest")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "guest_disabled"


def test_guest_signup_returns_key_that_works(database_url: str, storage: Path) -> None:
    with _guest_client(database_url, storage) as client:
        created = client.post("/v1/guest")
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["api_key"].startswith("qlm_")
        assert body["user"]["name"] == "Guest"
        assert body["user"]["email"].endswith(GUEST_EMAIL_SUFFIX)
        assert body["workspace"]["name"] == "My library"

        headers = {"X-API-Key": body["api_key"]}
        me = client.get("/v1/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["user"]["email"] == body["user"]["email"]
        assert me.json()["workspace"]["id"] == body["workspace"]["id"]

        uploaded = client.post(
            "/v1/documents",
            headers=headers,
            files={"file": ("note.txt", b"A short English note about the catalogue.", "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["status"] == "ready"


def test_guest_workspaces_are_private(database_url: str, storage: Path) -> None:
    with _guest_client(database_url, storage) as client:
        first = client.post("/v1/guest").json()
        second = client.post("/v1/guest").json()
        first_headers = {"X-API-Key": first["api_key"]}
        second_headers = {"X-API-Key": second["api_key"]}

        uploaded = client.post(
            "/v1/documents",
            headers=first_headers,
            files={"file": ("private.txt", b"Only the first guest may see this note.", "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.text
        document_id = uploaded.json()["id"]

        listing = client.get("/v1/documents", headers=second_headers)
        assert listing.status_code == 200
        assert listing.json()["total"] == 0
        assert client.get(f"/v1/documents/{document_id}", headers=second_headers).status_code == 404
        assert client.get(f"/v1/documents/{document_id}", headers=first_headers).status_code == 200


def test_guest_signup_rate_limit(database_url: str, storage: Path) -> None:
    with _guest_client(database_url, storage, guest_signups_per_minute=2) as client:
        assert client.post("/v1/guest").status_code == 201
        assert client.post("/v1/guest").status_code == 201
        blocked = client.post("/v1/guest")
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["code"] == "rate_limited"
        assert blocked.headers["retry-after"] == "60"


def test_guest_daily_upload_cap(database_url: str, storage: Path) -> None:
    with _guest_client(database_url, storage, guest_daily_uploads=2) as client:
        guest = client.post("/v1/guest").json()
        headers = {"X-API-Key": guest["api_key"]}
        for index in range(2):
            response = client.post(
                "/v1/documents",
                headers=headers,
                files={"file": (f"note-{index}.txt", b"Guest upload within the daily cap.", "text/plain")},
            )
            assert response.status_code == 201, response.text
        blocked = client.post(
            "/v1/documents",
            headers=headers,
            files={"file": ("too-many.txt", b"This should hit the guest upload limit.", "text/plain")},
        )
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["code"] == "upload_limit"

        owner_headers = {"X-API-Key": BOOTSTRAP_KEY}
        for index in range(3):
            response = client.post(
                "/v1/documents",
                headers=owner_headers,
                files={
                    "file": (
                        f"owner-{index}.txt",
                        b"Owner uploads stay uncapped by guest limits.",
                        "text/plain",
                    )
                },
            )
            assert response.status_code == 201, response.text
