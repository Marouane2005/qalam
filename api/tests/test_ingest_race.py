import threading
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from qalam.models import Chunk, Document, utcnow
from qalam.services import ingest
from qalam.services.ingest import STALE_AFTER, claim_document, process_document

pytestmark = pytest.mark.integration


def _upload(client: TestClient, headers: dict[str, str], text: str) -> uuid.UUID:
    response = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("note.txt", text.encode(), "text/plain")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "ready"
    return uuid.UUID(response.json()["id"])


def _set_status(
    client: TestClient, document_id: uuid.UUID, status: str, age: timedelta = timedelta(0)
) -> None:
    app: Any = client.app
    with app.state.session_factory() as session:
        session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=status, updated_at=utcnow() - age)
        )
        session.commit()


def test_concurrent_claims_let_exactly_one_ingest_run(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    document_id = _upload(client, auth_header, "The catalogue closes at noon on Sunday.")
    _set_status(client, document_id, "queued")
    app: Any = client.app
    barrier = threading.Barrier(4)
    winners: list[bool] = []
    lock = threading.Lock()

    def claim() -> None:
        with app.state.session_factory() as session:
            barrier.wait()
            won = claim_document(session, document_id) is not None
            with lock:
                winners.append(won)

    threads = [threading.Thread(target=claim) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(winners) == [False, False, False, True]


def test_a_second_run_skips_a_document_already_processing(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    document_id = _upload(client, auth_header, "The reading room opens at nine on Monday.")
    _set_status(client, document_id, "processing")
    app: Any = client.app
    with app.state.session_factory() as session:
        before = session.scalar(select(func.count()).where(Chunk.document_id == document_id))
        process_document(session, document_id, app.state.settings, app.state.llm)
        document = session.get(Document, document_id, populate_existing=True)
        assert document is not None
        assert document.status == "processing"
        after = session.scalar(select(func.count()).where(Chunk.document_id == document_id))
    assert before == after


def test_reprocess_is_refused_while_processing(client: TestClient, auth_header: dict[str, str]) -> None:
    document_id = _upload(client, auth_header, "The boiler inspection is booked for March.")
    _set_status(client, document_id, "processing")
    response = client.post(f"/v1/documents/{document_id}/reprocess", headers=auth_header)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "already_processing"


def test_a_stale_processing_document_can_be_reprocessed(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    document_id = _upload(client, auth_header, "The garden club meets on the first Tuesday.")
    _set_status(client, document_id, "processing", age=STALE_AFTER + timedelta(minutes=1))
    response = client.post(f"/v1/documents/{document_id}/reprocess", headers=auth_header)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready"


def test_a_failed_summary_keeps_the_document_ready(
    client: TestClient, auth_header: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("model down")

    monkeypatch.setattr(ingest, "summarize_text", fail)
    response = client.post(
        "/v1/documents",
        headers=auth_header,
        files={"file": ("note.txt", b"The library closes early on public holidays.", "text/plain")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["summary_short"] is None
    summary = client.get(f"/v1/documents/{body['id']}/summary", headers=auth_header)
    assert summary.status_code == 409


def test_reprocess_without_the_stored_file_keeps_the_document(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    document_id = _upload(client, auth_header, "The reading room reopens after the summer break.")
    app: Any = client.app
    with app.state.session_factory() as session:
        document = session.get(Document, document_id)
        assert document is not None
        Path(document.storage_path).unlink()
    response = client.post(f"/v1/documents/{document_id}/reprocess", headers=auth_header)
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "source_missing"
    detail = client.get(f"/v1/documents/{document_id}", headers=auth_header)
    assert detail.json()["status"] == "ready"
