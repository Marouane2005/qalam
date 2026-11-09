from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _watch_pool(client: TestClient) -> list[int]:
    """Record how many pooled connections are checked out during each model call."""

    app: Any = client.app
    pool = app.state.session_factory.kw["bind"].pool
    llm = app.state.llm
    original = llm.complete
    seen: list[int] = []

    def complete(*args: Any, **kwargs: Any) -> Any:
        seen.append(pool.checkedout())
        return original(*args, **kwargs)

    llm.complete = complete
    return seen


def test_model_calls_do_not_hold_a_database_connection(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    text = "The reading room closes at 18:00 on Fridays.\n\nThe boiler inspection is in March."
    uploaded = client.post(
        "/v1/documents",
        headers=auth_header,
        files={"file": ("memo.txt", text.encode(), "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]

    seen = _watch_pool(client)
    assert client.post(f"/v1/documents/{document_id}/summary", headers=auth_header).status_code == 200
    translated = client.post(
        f"/v1/documents/{document_id}/translations",
        headers=auth_header,
        json={"target_language": "fr"},
    )
    assert translated.status_code == 200, translated.text
    answered = client.post(
        "/v1/qa",
        headers=auth_header,
        json={"document_ids": [document_id], "question": "When does the reading room close?"},
    )
    assert answered.status_code == 200, answered.text
    extracted = client.post(
        "/v1/extract",
        headers=auth_header,
        json={
            "document_ids": [document_id],
            "json_schema": {"type": "object", "properties": {"closing": {"type": "string"}}},
        },
    )
    assert extracted.status_code == 200, extracted.text

    assert len(seen) >= 4
    assert all(count == 0 for count in seen), seen
