# Qalam

Qalam reads documents in Arabic, French and English. You upload a PDF, a scan, a Word file or plain text. It keeps the text layer when one exists, and OCRs the page when it does not. From there you can summarize a document, translate it between those three languages, ask questions that cite a page, or pull fields out of it with a JSON schema you supply.

The name is the Arabic word for a reed pen.

## What it does

- Accepts PDF, PNG, JPEG, TIFF, WebP, DOCX and TXT.
- Uses the embedded text of a PDF when it is real text, and Tesseract (`ara`, `fra`, `eng`) otherwise.
- Detects Arabic, French and English, then chunks the text and stores embeddings in Postgres with pgvector.
- Summarizes, translates, answers questions over one or many documents, and extracts fields against a JSON schema.
- Calls language models through an OpenAI-compatible chain: Inception Mercury, NVIDIA Build, LG EXAONE (via an OpenAI-compatible endpoint), OpenRouter, then a local mock. The mock is what runs when no keys are set.
- Keeps workspaces apart with API keys, limits request rate in Redis, and exposes `/health`, `/metrics` and an OpenAPI document.

## Architecture

```text
browser
  │
  ▼
Caddy  ── /v1, /health, /docs ──►  API (FastAPI)
  │                                  │
  └── everything else ──► Web       ├── Postgres 16 + pgvector
                           (Next.js) ├── Redis
                                      └── Celery worker
```

Ingestion is the slow part, so the API stores the file and a worker extracts, chunks, embeds and summarizes it. The web app polls until the document is ready. With `QALAM_TASKS_EAGER=1` the API does that work in the request, which is how the tests run.

```mermaid
flowchart LR
  upload[Upload] --> extract[Text or OCR]
  extract --> lang[Language]
  lang --> chunks[Chunks]
  chunks --> vectors[Embeddings]
  vectors --> store[(Postgres)]
  store --> read[Summary, translation, Q and A, extraction]
  read --> chain[Provider chain]
```

## Quickstart

You need Docker with Compose.

```sh
cp .env.example .env
docker compose up --build
```

Open [http://localhost](http://localhost). The API key is the value of `QALAM_BOOTSTRAP_API_KEY` in `.env`. The example ships with `change-me-please`. Change it before anyone else can reach the port.

![The library, with the four sample documents](docs/images/library.png)

![A document, with the extracted text beside the summary](docs/images/document.png)

![A question answered with a citation back to page 1](docs/images/question.png)

![Fields pulled from the sample invoice](docs/images/extract.png)

The chrome follows the language you pick. Arabic lays the page out from right to left.

![The same library with the interface in Arabic](docs/images/library-ar.png)

`QALAM_SEED_DEMO=1` loads four sample documents on first boot: an English memo as a PDF, a French note as a DOCX, an Arabic announcement as text, and a short invoice. They live in `samples/` and were written for this repository.

Try this on the English memo:

> When does the reading room close on Fridays?

The answer should mention 18:00 and cite a page. On the invoice, open Extract and use the example schema. `invoice_number` comes back as `INV-1042`.

The default chain ends at the mock provider, so the stack answers without any model key. Summaries are extractive. Translations keep the original paragraphs so you can check structure and right-to-left layout. Question answering picks the passage with the most words in common with the question. Field extraction looks for labels. Set a provider key when you want a model to write the text.

API docs are at [http://localhost/docs](http://localhost/docs). Prometheus metrics stay on the API process and are not published through Caddy:

```sh
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/metrics').read().decode().splitlines()[0])"
```

Stop the stack with `docker compose down`.

## Using it

The web app has four places:

- **Library** lists documents, with a language filter.
- **Upload** takes one or many files.
- **Document** shows the extracted text, a short and a longer summary, translation into Arabic, French or English, and a question box. Citations jump to the page.
- **Extract** takes a JSON schema and one or more documents.

The interface language (the chrome, not the documents) switches between Arabic, French and English. Arabic turns the layout right to left. The API key is stored in the browser only.

## API

Send `X-API-Key` or `Authorization: Bearer`.

```sh
KEY=change-me-please

curl -s http://localhost/v1/me -H "X-API-Key: $KEY"

curl -s -F "file=@samples/invoice-en.txt" \
  http://localhost/v1/documents \
  -H "X-API-Key: $KEY"

curl -s http://localhost/v1/qa \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"document_ids":["DOCUMENT_ID"],"question":"When does the reading room close on Fridays?"}'

curl -s http://localhost/v1/documents/DOCUMENT_ID/translations \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"target_language":"ar"}'

curl -s http://localhost/v1/extract \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"document_ids":["DOCUMENT_ID"],"schema":{"type":"object","properties":{"invoice_number":{"type":"string"},"total":{"type":"string"}},"required":["invoice_number","total"]}}'
```

Uploads return immediately with `status: queued` unless eager mode is on. Poll `GET /v1/documents/{id}` until `ready` or `failed`.

Other routes worth knowing: `POST /v1/workspaces` creates a workspace and returns a new key, `POST /v1/users` invites someone into the current workspace, `GET /v1/usage` sums tokens and latency for the workspace. Owners can invite. Members can read and upload. A key only sees its own workspace.

## Configuration

Everything is an environment variable. `.env.example` lists them. Compose overrides `QALAM_DATABASE_URL` and `QALAM_REDIS_URL` so the containers talk to `postgres` and `redis` even if `.env` still points at localhost.

| Variable | Purpose |
| --- | --- |
| `QALAM_BOOTSTRAP_API_KEY` | First owner key. Required for a usable install. |
| `QALAM_BOOTSTRAP_EMAIL` | Email of that owner. |
| `QALAM_SEED_DEMO` | Load the sample documents when the workspace is empty. |
| `QALAM_LLM_CHAIN` | Comma-separated provider order. |
| `QALAM_LLM_TIMEOUT_S` | Default timeout. `INCEPTION_TIMEOUT_S` and the same for the other providers override it. |
| `QALAM_LLM_RETRIES` | Retries after a timeout or a 408, 409, 429 or 5xx. Backoff doubles. |
| `QALAM_LLM_BREAKER_THRESHOLD` | Failures before a provider is skipped for `QALAM_LLM_BREAKER_COOLDOWN_S` seconds. |
| `QALAM_EMBEDDING_BACKEND` | `sentence-transformers` or `hash`. |
| `QALAM_RATE_LIMIT_PER_MINUTE` | Requests per API key. Redis down fails open and is logged. |
| `QALAM_SITE_ADDRESS` | Caddy site address. `:80` is plain HTTP. A hostname turns on automatic HTTPS. |
| `QALAM_TASKS_EAGER` | Run ingestion in the API process. Useful in tests. |

Provider keys are `INCEPTION_API_KEY`, `NVIDIA_API_KEY`, `EXAONE_API_KEY` and `OPENROUTER_API_KEY`. A provider with an empty key is skipped. If nothing in the chain can run, the mock is used.

Default endpoints:

- Inception Mercury: `https://api.inceptionlabs.ai/v1`, model `mercury-3`
- NVIDIA Build: `https://integrate.api.nvidia.com/v1`, model `meta/llama-3.3-70b-instruct`
- EXAONE: `https://api.friendli.ai/serverless/v1`, model `LGAI-EXAONE/EXAONE-4.0.1-32B`. Friendli hosts the OpenAI-compatible API. Point `EXAONE_BASE_URL` at another compatible server if you run the model yourself.
- OpenRouter: `https://openrouter.ai/api/v1`, model `openrouter/free`

Calls send `max_tokens` and a temperature of 0.7, which the current Mercury, NVIDIA and OpenRouter chat endpoints accept. Keys are not written to logs. Authorization headers and values that look like `qlm_…`, `sk-…` or `nvapi-…` are redacted. Prompts are not logged either.

Each successful call records provider, model, token counts and latency on the workspace, and the API process also exports `qalam_llm_*` Prometheus series.

## Embeddings

The intended model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions, the width of the `chunks.embedding` column). Install it with:

```sh
pip install -e "./api[embeddings]"
```

The first call downloads the weights. Set `QALAM_EMBEDDING_BACKEND=sentence-transformers`. If the package is missing or the model cannot load, Qalam logs `embedding_fallback` and uses a deterministic hashed bag-of-words vector instead. That is the path the tests use, and it is what the default image does, because the image does not ship PyTorch. The hash embedder is good enough for the demo and for keyword-style questions. Cross-language retrieval wants the sentence-transformer model.

To bake the model into an image, install the extra in a derived Dockerfile and mount a cache for `HF_HOME`.

## Development

Python 3.12, Node 22, and Postgres 16 with pgvector.

```sh
cd api
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
export QALAM_DATABASE_URL=postgresql+psycopg://qalam:qalam@127.0.0.1:5432/qalam
export QALAM_EMBEDDING_BACKEND=hash
export QALAM_LLM_CHAIN=mock
export QALAM_TASKS_EAGER=1
export QALAM_BOOTSTRAP_EMAIL=admin@example.com
export QALAM_BOOTSTRAP_API_KEY=change-me-please
export QALAM_SAMPLES_DIR="$PWD/../samples"
uvicorn qalam.main:app --reload --port 8000
```

In another shell:

```sh
cd web
npm install
npm run dev
```

The dev server proxies `/v1` to `http://127.0.0.1:8000`. Override that with `API_INTERNAL_URL` if the API is elsewhere. Redis is optional for this loop: rate limiting fails open and `/health` reports `degraded`.

Tests:

```sh
cd api
pytest
```

Integration tests use `QALAM_TEST_DATABASE_URL` when it is set, and otherwise start `pgvector/pgvector:pg16` with testcontainers. The mock provider is always used. OCR tests run when `tesseract` is on `PATH`.

```sh
ruff check .
mypy --package qalam
cd ../web && npm run lint && npm run typecheck && npm run build
```

Schema changes go in `api/alembic/versions`. `alembic upgrade head` runs when the API starts.

## Production notes

Put a real hostname in `QALAM_SITE_ADDRESS`, point DNS at the host, and set `ACME_EMAIL`. Caddy requests the certificate. Do not publish port 8000 on the public interface. The Compose file only publishes 80 and 443.

Change `POSTGRES_PASSWORD` and `QALAM_BOOTSTRAP_API_KEY`. The database password in the example is for a private machine.

See [SECURITY.md](SECURITY.md) for what this does and does not protect, and [CONTRIBUTING.md](CONTRIBUTING.md) if you want to send a change.

## License

MIT. Copyright 2026 Marouane El Aasri.
