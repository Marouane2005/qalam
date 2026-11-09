import os
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient

from qalam.main import create_app
from tests.helpers import BOOTSTRAP_KEY, make_settings

__all__ = ["BOOTSTRAP_KEY", "make_settings"]


def docker_available() -> bool:
    if os.environ.get("QALAM_TEST_DATABASE_URL"):
        return True
    sock_path = "/var/run/docker.sock"
    if not os.path.exists(sock_path):
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        sock.connect(sock_path)
        sock.close()
        return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    override = os.environ.get("QALAM_TEST_DATABASE_URL")
    if override:
        yield override
        return
    if not docker_available():
        pytest.skip("Set QALAM_TEST_DATABASE_URL or run Docker for integration tests")
    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:
        from testcontainers.postgres import PostgresContainer

    container = PostgresContainer(
        "pgvector/pgvector:pg16",
        username="qalam",
        password="qalam",
        dbname="qalam",
        driver="psycopg",
    )
    container.start()
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    path = tmp_path / "uploads"
    path.mkdir()
    return path


@pytest.fixture
def client(database_url: str, storage: Path) -> Iterator[TestClient]:
    settings = make_settings(database_url, storage)
    app = create_app(settings, redis_client=FakeRedis(decode_responses=True))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"X-API-Key": BOOTSTRAP_KEY}
