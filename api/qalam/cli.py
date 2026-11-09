import sys

from qalam.config import get_settings
from qalam.logging import configure_logging


def serve() -> None:
    import uvicorn

    settings = get_settings()
    configure_logging(settings.log_level)
    uvicorn.run("qalam.main:app", host=settings.host, port=settings.port)


def worker() -> None:
    from qalam.worker import celery_app

    level = get_settings().log_level
    celery_app.worker_main(argv=["worker", f"--loglevel={level}", "--concurrency=2"])


def seed() -> None:
    from qalam.db import session_factory
    from qalam.llm.client import build_client
    from qalam.migrate import migrate_with_retry
    from qalam.seed import seed_if_empty

    settings = get_settings()
    configure_logging(settings.log_level)
    migrate_with_retry(settings.database_url)
    llm = build_client(settings)
    with session_factory(settings)() as session:
        seed_if_empty(session, settings, llm, force=True)


def reindex() -> None:
    from qalam.db import session_factory
    from qalam.migrate import migrate_with_retry
    from qalam.services.ingest import reindex_embeddings

    settings = get_settings()
    configure_logging(settings.log_level)
    migrate_with_retry(settings.database_url)
    with session_factory(settings)() as session:
        count = reindex_embeddings(session, settings)
    print(f"Re-embedded {count} chunks with the {settings.embedding_backend} backend.")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if command == "serve":
        serve()
    elif command == "worker":
        worker()
    elif command == "seed":
        seed()
    elif command == "reindex":
        reindex()
    else:
        raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
