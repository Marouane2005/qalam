# Single-container image for small free hosts that run one web service.
# It runs the API, the web app and a local Redis in one container. Ingestion
# runs inside the upload request (QALAM_TASKS_EAGER=1), so there is no worker.
# Postgres with pgvector is external and comes in through QALAM_DATABASE_URL.

FROM node:22-bookworm-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS web

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

FROM node:22-bookworm-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS node

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    QALAM_STORAGE_DIR=/var/lib/qalam/uploads \
    QALAM_SAMPLES_DIR=/app/samples \
    QALAM_TASKS_EAGER=1 \
    QALAM_EMBEDDING_BACKEND=hash \
    QALAM_REDIS_URL=redis://127.0.0.1:6379/0 \
    QALAM_HOST=127.0.0.1 \
    QALAM_PORT=8000 \
    API_INTERNAL_URL=http://127.0.0.1:8000 \
    HOSTNAME=0.0.0.0 \
    PORT=10000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-fra \
        tesseract-ocr-eng \
        fonts-dejavu-core \
        redis-server \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin qalam

COPY --from=node /usr/local/bin/node /usr/local/bin/node

WORKDIR /app

COPY api/pyproject.toml api/README.md api/alembic.ini ./
COPY api/qalam ./qalam
COPY api/alembic ./alembic
COPY samples ./samples

RUN pip install --no-cache-dir .

COPY --from=web --chown=qalam:qalam /app/.next/standalone ./web/
COPY --from=web --chown=qalam:qalam /app/.next/static ./web/.next/static
COPY --from=web --chown=qalam:qalam /app/public ./web/public

COPY deploy/render/start.sh /start.sh
RUN chmod 755 /start.sh \
    && mkdir -p /var/lib/qalam/uploads \
    && chown -R qalam:qalam /var/lib/qalam

USER qalam
EXPOSE 10000
CMD ["/start.sh"]
