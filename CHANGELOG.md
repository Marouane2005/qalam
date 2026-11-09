# Changelog

## 0.1.0 - 2026-11-09

First public version.

- Upload PDF, images, DOCX and TXT, with Tesseract when a PDF has no text layer.
- Language detection, chunking and pgvector embeddings, with a hash embedder when sentence-transformers is not installed.
- Summaries, translation between Arabic, French and English, question answering with page citations, and JSON-schema extraction.
- OpenAI-compatible provider chain for Inception Mercury, NVIDIA Build, EXAONE and OpenRouter, plus a mock provider.
- Per-provider timeouts, retries, a circuit breaker, and token and latency accounting.
- API keys, workspaces, Redis rate limits, JSON logs, `/health` and `/metrics`.
- Next.js interface with an Arabic, French and English language switch and right-to-left layout.
- Docker Compose, Caddy, and a CI workflow.
