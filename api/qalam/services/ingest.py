import re
import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import ColumnElement, and_, delete, or_, select, update
from sqlalchemy.orm import Session

from qalam.config import Settings
from qalam.errors import IngestError
from qalam.llm.client import LLMClient
from qalam.logging import get_logger
from qalam.metrics import DOCUMENTS, INGEST_LATENCY
from qalam.models import Chunk, Document, Translation, utcnow
from qalam.services.reading import Summary, document_text, summarize_text
from qalam.services.usage import record_usage
from qalam.text.chunk import chunk_pages
from qalam.text.embed import embed_texts
from qalam.text.extract import extract_pages
from qalam.text.language import detect_language

log = get_logger("qalam.ingest")

ALLOWED = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


def safe_filename(name: str) -> str:
    base = Path(name or "document").name
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u0600-\u06FF ]", "_", base).strip(" .")
    return (cleaned or "document")[:180]


def sniff(data: bytes, suffix: str) -> bool:
    if suffix == ".pdf":
        return data.startswith(b"%PDF")
    if suffix == ".png":
        return data.startswith(b"\x89PNG")
    if suffix in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8")
    if suffix == ".webp":
        return len(data) >= 12 and data[8:12] == b"WEBP"
    if suffix in {".tif", ".tiff"}:
        return data.startswith(b"II*\x00") or data.startswith(b"MM\x00*")
    if suffix == ".docx":
        return data.startswith(b"PK")
    if suffix == ".txt":
        sample = data[:4096]
        for encoding in ("utf-8", "cp1256", "latin-1"):
            try:
                sample.decode(encoding)
                return True
            except UnicodeDecodeError:
                continue
    return False


def store_bytes(
    session: Session,
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> Document:
    if len(data) > settings.max_upload_bytes:
        raise IngestError("The file is larger than the upload limit.")
    safe = safe_filename(filename)
    suffix = Path(safe).suffix.lower()
    media_type = ALLOWED.get(suffix)
    if media_type is None:
        raise IngestError("Upload a PDF, image, DOCX, or TXT file.")
    if not sniff(data, suffix):
        raise IngestError("The file contents do not match its extension.")
    document_id = uuid.uuid4()
    directory = Path(settings.storage_dir) / str(workspace_id) / str(document_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / safe
    path.write_bytes(data)
    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        filename=safe,
        media_type=media_type,
        byte_size=len(data),
        storage_path=str(path),
        status="queued",
    )
    session.add(document)
    session.commit()
    return document


# A document stuck in "processing" this long is treated as abandoned, for example
# after a worker crash, and can be claimed again.
STALE_AFTER = timedelta(minutes=15)


def _claimable(*statuses: str) -> ColumnElement[bool]:
    stale = utcnow() - STALE_AFTER
    return or_(
        Document.status.in_(statuses),
        and_(Document.status == "processing", Document.updated_at < stale),
    )


def claim_document(session: Session, document_id: uuid.UUID) -> Document | None:
    """Atomically move a queued document to processing.

    Returns the document when this caller won the claim, or None when it does not
    exist or another run is already processing it. The conditional UPDATE makes
    concurrent claims safe: Postgres re-checks the status after the row lock, so
    only one caller sees a row come back.
    """

    claimed = session.execute(
        update(Document)
        .where(Document.id == document_id, _claimable("queued"))
        .values(status="processing", error=None, updated_at=utcnow())
        .returning(Document.id)
    ).scalar_one_or_none()
    session.commit()
    if claimed is None:
        return None
    return session.get(Document, document_id, populate_existing=True)


def requeue_document(session: Session, document: Document) -> bool:
    """Mark a document queued for another run unless one is already in progress."""

    requeued = session.execute(
        update(Document)
        .where(
            Document.id == document.id,
            _claimable("queued", "ready", "failed"),
        )
        .values(status="queued", error=None, updated_at=utcnow())
        .returning(Document.id)
    ).scalar_one_or_none()
    session.commit()
    if requeued is None:
        return False
    session.refresh(document)
    return True


def process_document(
    session: Session,
    document_id: uuid.UUID,
    settings: Settings,
    llm: LLMClient,
) -> None:
    started = time.perf_counter()
    document = claim_document(session, document_id)
    if document is None:
        log.info("ingest_skipped", document_id=str(document_id))
        return
    # End the read transaction so no connection or row lock is held during extraction,
    # embedding and the model call.
    session.commit()
    try:
        pages = extract_pages(Path(document.storage_path), document.media_type)
        drafts = chunk_pages(
            [(page.number, page.text) for page in pages],
            settings.chunk_size,
            settings.chunk_overlap,
        )
        if not drafts:
            raise IngestError("No text could be extracted from this file.")
        vectors = embed_texts([draft.text for draft in drafts], settings)
        body = "\n\n".join(page.text.strip() for page in pages if page.text.strip())
        language = detect_language(body)

        session.execute(delete(Chunk).where(Chunk.document_id == document.id))
        session.execute(delete(Translation).where(Translation.document_id == document.id))
        for draft, vector in zip(drafts, vectors, strict=True):
            session.add(
                Chunk(
                    document_id=document.id,
                    page=draft.page,
                    position=draft.position,
                    text=draft.text,
                    char_start=draft.char_start,
                    char_end=draft.char_end,
                    embedding=vector,
                )
            )
        document.language = language
        document.page_count = max(page.number for page in pages)
        document.pages = [{"page": page.number, "text": page.text} for page in pages]
        document.summary_short = None
        document.summary_detailed = None
        document.summary_provider = None
        document.updated_at = utcnow()
        session.commit()

        # The summary runs outside any transaction. If it fails, the text and chunks
        # are already saved and the document is still usable; the summary can be
        # regenerated later.
        summary: Summary | None
        try:
            summary = summarize_text(body, language, llm, settings.llm_input_chars)
        except Exception as exc:
            log.warning("summary_failed", document_id=str(document_id), error=type(exc).__name__)
            summary = None
        if summary is not None:
            record_usage(session, document.workspace_id, "summarize", summary.completion)
            document.summary_short = summary.short
            document.summary_detailed = summary.detailed
            document.summary_provider = summary.provider
        document.status = "ready"
        document.error = None
        document.updated_at = utcnow()
        session.commit()
        DOCUMENTS.labels("ready").inc()
    except IngestError as exc:
        _mark_failed(session, document_id, exc.message)
        DOCUMENTS.labels("failed").inc()
    except Exception as exc:
        log.error("ingest_failed", document_id=str(document_id), error=type(exc).__name__)
        _mark_failed(session, document_id, "Ingestion failed.")
        DOCUMENTS.labels("failed").inc()
    finally:
        INGEST_LATENCY.observe(time.perf_counter() - started)


def _mark_failed(session: Session, document_id: uuid.UUID, message: str) -> None:
    session.rollback()
    document = session.get(Document, document_id)
    if document is None:
        return
    document.status = "failed"
    document.error = message[:500]
    document.updated_at = utcnow()
    session.commit()


def delete_document(session: Session, document: Document) -> None:
    path = Path(document.storage_path)
    workspace_dir = path.parent
    session.delete(document)
    session.commit()
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir, ignore_errors=True)


def load_workspace_document(
    session: Session,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document | None:
    return session.scalar(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    )


def joined_text(document: Document, limit: int) -> str:
    return document_text(document)[:limit]
