import json
import uuid
from pathlib import Path

import pymupdf
import pytest
from docx import Document
from fakeredis import FakeRedis
from fastapi.testclient import TestClient

from qalam.main import create_app
from tests.helpers import BOOTSTRAP_KEY, make_settings

pytestmark = pytest.mark.integration

INVOICE_SCHEMA = {
    "type": "object",
    "required": ["invoice_number", "total"],
    "properties": {
        "invoice_number": {"type": "string"},
        "date": {"type": "string"},
        "seller": {"type": "string"},
        "buyer": {"type": "string"},
        "total": {"type": "string"},
        "currency": {"type": "string"},
    },
}


def _upload(
    client: TestClient,
    headers: dict[str, str],
    name: str,
    data: bytes,
    content_type: str,
) -> dict[str, object]:
    response = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": (name, data, content_type)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def test_health_metrics_and_auth(client: TestClient, auth_header: dict[str, str]) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["database"] == "ok"
    assert health.json()["redis"] == "ok"
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers={"X-API-Key": "qlm_not_a_real_key"}).status_code == 401
    me = client.get("/v1/me", headers=auth_header)
    assert me.status_code == 200
    body = me.json()
    assert body["workspace"]["name"] == "Library"
    assert body["providers"] == ["mock"]
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "qalam_http_requests_total" in metrics.text


def test_english_document_summary_qa_and_translation(client: TestClient, auth_header: dict[str, str]) -> None:
    text = (
        "The reading room closes at 18:00 on Fridays.\n\n"
        "The boiler inspection is booked for 19 March 2026.\n\n"
        "Ada will lead the children's hour on Thursday."
    )
    document = _upload(client, auth_header, "memo.txt", text.encode(), "text/plain")
    assert document["status"] == "ready"
    assert document["language"] == "en"
    assert "18:00" in str(document["summary_short"])

    summary = client.get(f"/v1/documents/{document['id']}/summary", headers=auth_header)
    assert summary.status_code == 200
    regenerated = client.post(f"/v1/documents/{document['id']}/summary", headers=auth_header)
    assert regenerated.status_code == 200

    answer = client.post(
        "/v1/qa",
        headers=auth_header,
        json={
            "document_ids": [document["id"]],
            "question": "When does the reading room close on Fridays?",
        },
    )
    assert answer.status_code == 200, answer.text
    payload = answer.json()
    assert "18:00" in payload["answer"]
    assert payload["citations"][0]["page"] == 1
    assert payload["citations"][0]["filename"] == "memo.txt"
    listed = client.get(f"/v1/documents/{document['id']}/questions", headers=auth_header)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    translated = client.post(
        f"/v1/documents/{document['id']}/translations",
        headers=auth_header,
        json={"target_language": "ar"},
    )
    assert translated.status_code == 200, translated.text
    body = translated.json()
    assert body["direction"] == "rtl"
    assert len(body["paragraphs"]) == 3
    fetched = client.get(
        f"/v1/documents/{document['id']}/translations/ar",
        headers=auth_header,
    )
    assert fetched.status_code == 200
    assert fetched.json()["text"] == body["text"]


def test_french_docx_and_arabic_text(client: TestClient, auth_header: dict[str, str], tmp_path: Path) -> None:
    french = (
        "L'atelier se réunit chaque mardi à 19 h 30 dans la salle des cartes. "
        "La cotisation annuelle est de 40 euros pour chaque adhérent de la coopérative."
    )
    docx_path = tmp_path / "atelier.docx"
    document = Document()
    document.add_paragraph(french)
    document.save(docx_path)
    uploaded = _upload(
        client,
        auth_header,
        "atelier.docx",
        docx_path.read_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert uploaded["language"] == "fr"
    text = client.get(f"/v1/documents/{uploaded['id']}/text", headers=auth_header)
    assert "cotisation" in text.text

    arabic = "تُقام الورشة يوم السبت 18 أبريل 2026 في قاعة الطابق الثاني. الرسم للفرد عشرون درهماً."
    arabic_doc = _upload(client, auth_header, "warsha.txt", arabic.encode(), "text/plain")
    assert arabic_doc["language"] == "ar"
    answer = client.post(
        "/v1/qa",
        headers=auth_header,
        json={"document_ids": [arabic_doc["id"]], "question": "متى تُقام الورشة؟"},
    )
    assert answer.status_code == 200
    assert "أبريل" in answer.json()["answer"] or "الورشة" in answer.json()["answer"]


def test_pdf_round_trip_and_invoice_extraction(
    client: TestClient, auth_header: dict[str, str], tmp_path: Path
) -> None:
    pdf_path = tmp_path / "invoice.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Invoice: INV-1042")
    page.insert_text((72, 96), "Date: 2026-03-02")
    page.insert_text((72, 120), "Seller: Northwind Studio")
    page.insert_text((72, 144), "Buyer: The Lantern Library")
    page.insert_text((72, 168), "Total: 900.00 EUR")
    pdf.save(pdf_path)
    pdf.close()
    document = _upload(client, auth_header, "invoice.pdf", pdf_path.read_bytes(), "application/pdf")
    assert document["status"] == "ready"
    extracted = client.post(
        "/v1/extract",
        headers=auth_header,
        json={"document_ids": [document["id"]], "schema": INVOICE_SCHEMA},
    )
    assert extracted.status_code == 200, extracted.text
    result = extracted.json()["result"]
    assert result["invoice_number"] == "INV-1042"
    assert result["seller"] == "Northwind Studio"
    assert "900.00" in result["total"]
    usage = client.get("/v1/usage", headers=auth_header)
    assert usage.status_code == 200
    assert any(row["operation"] == "extract" for row in usage.json())


def test_workspace_isolation_and_roles(client: TestClient, auth_header: dict[str, str]) -> None:
    document = _upload(
        client,
        auth_header,
        "private.txt",
        b"This note belongs to the first workspace only.",
        "text/plain",
    )
    created = client.post("/v1/workspaces", headers=auth_header, json={"name": "Annex"})
    assert created.status_code == 201, created.text
    other_key = created.json()["api_key"]
    other_headers = {"X-API-Key": other_key}
    listing = client.get("/v1/documents", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 0
    hidden = client.get(f"/v1/documents/{document['id']}", headers=other_headers)
    assert hidden.status_code == 404

    invited = client.post(
        "/v1/users",
        headers=auth_header,
        json={"email": "sara@example.com", "name": "Sara", "role": "member"},
    )
    assert invited.status_code == 201, invited.text
    member_headers = {"X-API-Key": invited.json()["api_key"]}
    visible = client.get(f"/v1/documents/{document['id']}", headers=member_headers)
    assert visible.status_code == 200
    denied = client.post(
        "/v1/users",
        headers=member_headers,
        json={"email": "sam@example.com", "name": "Sam"},
    )
    assert denied.status_code == 403

    removed = client.delete(f"/v1/documents/{document['id']}", headers=auth_header)
    assert removed.status_code == 204
    assert client.get(f"/v1/documents/{document['id']}", headers=auth_header).status_code == 404


def test_rejects_a_mismatched_upload_and_unknown_document(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    response = client.post(
        "/v1/documents",
        headers=auth_header,
        files={"file": ("notes.pdf", b"this is not a pdf", "application/pdf")},
    )
    assert response.status_code == 422
    missing = client.get(f"/v1/documents/{uuid.uuid4()}", headers=auth_header)
    assert missing.status_code == 404
    bad_schema = client.post(
        "/v1/extract",
        headers=auth_header,
        json={"document_ids": [str(uuid.uuid4())], "schema": {"type": "string"}},
    )
    assert bad_schema.status_code == 404


def test_rate_limit_on_a_small_window(database_url: str, storage: Path) -> None:
    settings = make_settings(database_url, storage, rate_limit_per_minute=2)
    app = create_app(settings, redis_client=FakeRedis(decode_responses=True))
    with TestClient(app) as client:
        headers = {"X-API-Key": BOOTSTRAP_KEY}
        assert client.get("/v1/me", headers=headers).status_code == 200
        assert client.get("/v1/me", headers=headers).status_code == 200
        blocked = client.get("/v1/me", headers=headers)
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
        assert client.get("/health").status_code == 200


def test_bearer_header_is_accepted(client: TestClient) -> None:
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {BOOTSTRAP_KEY}"})
    assert response.status_code == 200


def test_reprocess_runs_again(client: TestClient, auth_header: dict[str, str]) -> None:
    document = _upload(
        client,
        auth_header,
        "again.txt",
        b"The catalogue closes at noon on Sunday and opens at nine on Monday.",
        "text/plain",
    )
    response = client.post(f"/v1/documents/{document['id']}/reprocess", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_worker_ignores_a_missing_document(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QALAM_DATABASE_URL", database_url)
    monkeypatch.setenv("QALAM_LLM_CHAIN", "mock")
    monkeypatch.setenv("QALAM_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("QALAM_LOG_LEVEL", "WARNING")
    from qalam.migrate import migrate
    from qalam.worker import ingest_document

    migrate(database_url)
    missing = str(uuid.uuid4())
    assert ingest_document.run(missing) == missing


def test_library_lists_only_this_workspace(client: TestClient, auth_header: dict[str, str]) -> None:
    _upload(client, auth_header, "one.txt", b"One short English note about the catalogue.", "text/plain")
    listing = client.get("/v1/documents", headers=auth_header)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    assert all("storage_path" not in item for item in body["items"])
    # The OpenAPI document stays public.
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    assert "/v1/qa" in spec.json()["paths"]
    json.dumps(body)
