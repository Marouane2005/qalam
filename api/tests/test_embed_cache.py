import sys
import types
from collections.abc import Iterator

import pytest

from qalam.config import Settings
from qalam.text import embed


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    embed._load_model.cache_clear()
    embed._sentence_transformers_installed.cache_clear()
    yield
    embed._load_model.cache_clear()
    embed._sentence_transformers_installed.cache_clear()


def _settings() -> Settings:
    return Settings(embedding_backend="sentence-transformers", embedding_dim=3, llm_chain="mock")


def _fake_package(monkeypatch: pytest.MonkeyPatch, loads: list[str], fail: bool = False) -> None:
    class FakeModel:
        def __init__(self, name: str) -> None:
            if fail:
                raise RuntimeError("download failed")
            loads.append(name)

        def encode(self, texts: list[str], normalize_embeddings: bool) -> list[list[float]]:
            return [[1.0, 0.0, 0.0] for _ in texts]

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


def test_model_is_loaded_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[str] = []
    _fake_package(monkeypatch, loads)
    settings = _settings()
    for _ in range(3):
        assert embed.embed_texts(["hello"], settings) == [[1.0, 0.0, 0.0]]
    assert loads == [settings.embedding_model]


def test_missing_package_falls_back_to_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    settings = _settings()
    assert embed.embed_texts(["hello"], settings) == [embed.hash_embed("hello", 3)]


def test_model_failure_is_raised_not_mixed_with_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_package(monkeypatch, [], fail=True)
    with pytest.raises(RuntimeError):
        embed.embed_texts(["hello"], _settings())
