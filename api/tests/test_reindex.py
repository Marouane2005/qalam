import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from qalam.models import Chunk
from qalam.services import ingest
from qalam.services.ingest import reindex_embeddings

pytestmark = pytest.mark.integration


def test_reindex_rewrites_every_chunk_with_the_current_embedder(
    client: TestClient, auth_header: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = []
    for name, text in [
        ("one.txt", "The reading room closes at 18:00 on Fridays."),
        ("two.txt", "The garden club meets on the first Tuesday of the month."),
    ]:
        response = client.post(
            "/v1/documents",
            headers=auth_header,
            files={"file": (name, text.encode(), "text/plain")},
        )
        assert response.status_code == 201, response.text
        ids.append(uuid.UUID(response.json()["id"]))

    app: Any = client.app
    marker = [1.0] + [0.0] * 383

    def fake_embed(texts: list[str], _settings: object) -> list[list[float]]:
        return [marker for _ in texts]

    monkeypatch.setattr(ingest, "embed_texts", fake_embed)
    with app.state.session_factory() as session:
        total = len(session.scalars(select(Chunk.id)).all())
        assert reindex_embeddings(session, app.state.settings, batch_size=1) == total
        rows = session.scalars(select(Chunk).where(Chunk.document_id.in_(ids))).all()
        assert rows
        assert all(list(row.embedding) == marker for row in rows)
