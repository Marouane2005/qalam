FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QALAM_STORAGE_DIR=/var/lib/qalam/uploads \
    QALAM_SAMPLES_DIR=/app/samples

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-fra \
        tesseract-ocr-eng \
        fonts-dejavu-core \
        gosu \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin qalam

WORKDIR /app

COPY api/pyproject.toml api/README.md api/alembic.ini ./
COPY api/qalam ./qalam
COPY api/alembic ./alembic
COPY samples ./samples

RUN pip install --no-cache-dir .

COPY api/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "qalam.cli", "serve"]
