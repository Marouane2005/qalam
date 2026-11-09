import uuid

from celery import Celery
from celery.signals import worker_process_init

from qalam.config import get_settings
from qalam.db import reset_engine, session_factory
from qalam.errors import IngestError
from qalam.llm.client import build_client
from qalam.logging import configure_logging, get_logger
from qalam.services.ingest import process_document

log = get_logger("qalam.worker")
settings = get_settings()
configure_logging(settings.log_level)

celery_app = Celery("qalam", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@worker_process_init.connect
def _reset_db_pool(**_kwargs: object) -> None:
    reset_engine()


@celery_app.task(name="qalam.ingest_document")
def ingest_document(document_id: str) -> str:
    current = get_settings()
    llm = build_client(current)
    with session_factory(current)() as session:
        try:
            process_document(session, uuid.UUID(document_id), current, llm)
        except IngestError:
            return document_id
    return document_id
