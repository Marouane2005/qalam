# Contributing

Thanks for looking. Qalam is a small codebase on purpose: an API, a worker, and a web client.

## Setup

Follow the Development section of the README. You will want Python 3.12, Node 22, and Postgres 16 with the `vector` extension. Redis is only required if you want to exercise rate limits.

Run the tests from `api/`:

```sh
pip install -e ".[dev]"
pytest
```

Set `QALAM_TEST_DATABASE_URL` if you already have Postgres. Otherwise Docker has to be available so testcontainers can start `pgvector/pgvector:pg16`.

Before sending a change:

```sh
cd api && ruff check . && mypy --package qalam && pytest
cd web && npm run lint && npm run typecheck && npm run build
```

## Style

Python is formatted with Ruff. Line length is 110. New code should be typed; `mypy --package qalam` is part of CI. The web app is TypeScript with the App Router and Tailwind.

Prefer a straight function over a new abstraction. Comments are for the bit that would surprise the next reader, not for the name of the function.

## Migrations

Add a revision under `api/alembic/versions`. Do not edit a revision that has already shipped. The embedding column is `vector(384)`. A different model width needs a migration, not a silent cast.

## Providers and secrets

Do not commit an `.env`. Tests use the mock provider. If you add a provider, it has to read its key from the environment, omit the key from `__repr__` and from logs, and sit in the chain behind a circuit breaker like the others.

## Pull requests

Describe what changed and how you checked it. A screenshot helps when the web UI moves. Keep the change focused.
