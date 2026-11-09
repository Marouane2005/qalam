FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

ARG QALAM_EXTRAS=embeddings
ARG QALAM_PRELOAD_EMBEDDING_MODEL=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QALAM_STORAGE_DIR=/var/lib/qalam/uploads \
    QALAM_SAMPLES_DIR=/app/samples \
    HF_HOME=/var/lib/qalam/hf-cache \
    TRANSFORMERS_CACHE=/var/lib/qalam/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/var/lib/qalam/hf-cache \
    HUGGINGFACE_HUB_CACHE=/var/lib/qalam/hf-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-fra \
        tesseract-ocr-eng \
        fonts-dejavu-core \
        gosu \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin qalam \
    && mkdir -p /var/lib/qalam/uploads /var/lib/qalam/hf-cache \
    && chown -R qalam:qalam /var/lib/qalam

WORKDIR /app

COPY api/pyproject.toml api/README.md api/alembic.ini ./
COPY api/qalam ./qalam
COPY api/alembic ./alembic
COPY samples ./samples

# Prefer the CPU wheel index so embeddings builds stay lean (no CUDA).
# Pass --build-arg QALAM_EXTRAS= for a slim image without sentence-transformers.
RUN if [ -n "${QALAM_EXTRAS}" ]; then \
      pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        ".[${QALAM_EXTRAS}]"; \
    else \
      pip install --no-cache-dir .; \
    fi

# Optional: bake the embedding weights into the image (off by default).
RUN if [ -n "${QALAM_PRELOAD_EMBEDDING_MODEL}" ]; then \
      gosu qalam python -c \
        "from sentence_transformers import SentenceTransformer; SentenceTransformer('${QALAM_PRELOAD_EMBEDDING_MODEL}')"; \
    fi

COPY api/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "qalam.cli", "serve"]
