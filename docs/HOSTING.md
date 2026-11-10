# Free hosting on Render and Neon

This runs the public demo at no cost and without a payment card:

- **Render** free web service runs one container built from
  `deploy/render/Dockerfile`. It holds the web app, the API and a local Redis.
  Uploads are processed inside the request (`QALAM_TASKS_EAGER=1`), so there is
  no Celery worker.
- **Neon** free Postgres holds the data. pgvector is available on the free plan,
  and the first migration runs `CREATE EXTENSION IF NOT EXISTS vector`.

The image uses the local hash embedder (`QALAM_EMBEDDING_BACKEND=hash`). The
free instance has 512 MB of memory, which is not enough for torch and the
sentence-transformers model.

## Limits to know about

- Render stops a free service after 15 minutes without traffic. The next visit
  wakes it in about a minute and shows Render's loading page meanwhile.
- The container disk is not kept. Extracted text, chunks, summaries and
  vectors live in Neon and survive restarts. The original uploaded file does
  not, so reprocessing an old upload after a restart fails until it is
  uploaded again.
- Neon stops its compute after 5 minutes idle and gives each project 100
  CU-hours a month and 1 GB of storage.
- Uploads are capped at 5 MB here (`QALAM_MAX_UPLOAD_BYTES`), because OCR of a
  large scan in the request can exceed the free memory.
- Guest access is on (`QALAM_GUEST_ACCESS=1`). Visitors get a private library
  via `POST /v1/guest`, limited to 3 signups per IP per minute and 20 uploads
  per guest library per day.

## Set up

1. Neon: create a project (Postgres 16 or newer, region close to Frankfurt) and
   copy the **direct** connection string, not the `-pooler` one. A plain
   `postgresql://...?sslmode=require` URL is fine; Qalam switches it to the
   psycopg driver itself.
2. Render: New > Blueprint, pick this repository. Render reads `render.yaml`
   and asks for the values marked `sync: false`:
   - `QALAM_DATABASE_URL`: the Neon connection string.
   - `QALAM_BOOTSTRAP_API_KEY`: a long random string. It is the key you type in
     the web app to sign in.
   - `INCEPTION_API_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`: optional. Leave
     them empty to use the built-in mock provider.
3. Wait for the first deploy. The site is at `https://<service>.onrender.com`,
   and `/health` should return `{"status": "ok", ...}`.

Every push to `main` redeploys. To deploy by hand, use Manual Deploy in the
Render dashboard.
