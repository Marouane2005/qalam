import hashlib
import math
import re
from functools import lru_cache
from typing import Any

from qalam.config import Settings
from qalam.logging import get_logger

log = get_logger("qalam.embed")

_TOKEN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


def hash_embed(text: str, dim: int = 384) -> list[float]:
    """Bag-of-tokens vector. Stable, local, and good enough for tests and demos."""

    vector = [0.0] * dim
    for token in _TOKEN.findall(text.lower()):
        digest = hashlib.blake2s(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


@lru_cache(maxsize=4)
def _load_model(name: str) -> Any:
    """Load a sentence-transformers model once per process and reuse it."""

    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name)


@lru_cache(maxsize=1)
def _sentence_transformers_installed() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        log.error("embedding_backend_missing", backend="sentence-transformers", fallback="hash")
        return False
    return True


def _sentence_transformer_vectors(texts: list[str], settings: Settings) -> list[list[float]]:
    model = _load_model(settings.embedding_model)
    encoded = model.encode(texts, normalize_embeddings=True)
    vectors: list[list[float]] = []
    for row in encoded:
        values = [float(item) for item in row]
        if len(values) != settings.embedding_dim:
            raise ValueError(
                f"Model {settings.embedding_model} returned {len(values)} dimensions, "
                f"expected {settings.embedding_dim}"
            )
        vectors.append(values)
    return vectors


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    if not texts:
        return []
    backend = settings.embedding_backend
    if backend == "hash":
        return [hash_embed(text, settings.embedding_dim) for text in texts]
    if backend == "sentence-transformers":
        # Fall back only when the package is not installed at all. That is fixed for the
        # life of the image, so stored vectors and query vectors always come from the
        # same embedder. Any other failure is raised instead of silently mixing
        # hash vectors into an index built with the model.
        if not _sentence_transformers_installed():
            return [hash_embed(text, settings.embedding_dim) for text in texts]
        return _sentence_transformer_vectors(texts, settings)
    raise ValueError(f"Unknown embedding backend: {backend}")
