# Security

Qalam is a self-hosted service. You run it, and you hold the documents.

## Reporting

Open a private security advisory on GitHub, or email the maintainer if the repository has no advisory form yet. Please give a way to reproduce the issue and wait for a fix before writing about it in public.

## What the application does

- API keys are stored as SHA-256 hashes. The raw key is returned once, when it is created.
- A key is bound to one workspace. Queries filter on that workspace.
- Uploads are limited to 25 MB by default, checked against an extension allow-list, and sniffed so a renamed file is rejected.
- Filenames are stripped of path segments.
- Logs redact `Authorization` values and strings that look like `qlm_`, `sk-` or `nvapi-` keys. Prompts and document text are not logged.
- Rate limits are counted in Redis per key.

## What you still have to decide

- The bootstrap key in `.env.example` is a placeholder. Replace it, and replace `POSTGRES_PASSWORD`, before the host is reachable.
- `/health` and the interactive docs are on the public proxy. `/metrics` is not, but it is unauthenticated on the API port. Do not publish port 8000.
- Caddy does not set a Content-Security-Policy. Add one if you front the site with a stricter policy.
- When a provider key is set, document text is sent to that provider. The mock provider stays on the machine. If that is not acceptable, leave the keys empty or point `EXAONE_BASE_URL` (or another base URL) at a model you run yourself.
- Documents can contain instructions aimed at the model. The prompts tell the model to treat the document as data. That is not a guarantee. Do not point extraction at a schema you would not want a hostile document to influence, and do not treat the model output as an authority on its own.
- OCR and parsing libraries have had security bugs. Keep the image updated.
- There is no password login. Anyone who holds a key is that user. Revoke a key by setting `revoked_at` on the `api_keys` row, or stop handing the key out.
- Uploaded files sit on the `uploads` volume. Back it up with the database, and treat the volume as sensitive.

## Scope

This is not a multi-tenant hosting product. Workspaces are a boundary inside one installation, not a promise about noisy neighbours on a shared kernel.
