import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from qalam.auth import Principal
from qalam.deps import get_principal, get_session
from qalam.errors import AppError
from qalam.logging import get_logger
from qalam.models import Document
from qalam.schemas import DocumentDetail, DocumentList, DocumentOut, DocumentText, PageOut
from qalam.services.ingest import (
    delete_document,
    load_workspace_document,
    process_document,
    requeue_document,
    store_bytes,
)

log = get_logger("qalam.documents")
router = APIRouter(prefix="/v1", tags=["documents"])


def _require_document(session: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    document = load_workspace_document(session, principal.workspace.id, document_id)
    if document is None:
        raise AppError("not_found", "Document not found.", 404)
    return document


def _queue(request: Request, session: Session, document: Document) -> Document:
    settings = request.app.state.settings
    if settings.tasks_eager:
        process_document(session, document.id, settings, request.app.state.llm)
        session.refresh(document)
        return document
    try:
        from qalam.worker import ingest_document

        ingest_document.delay(str(document.id))
    except Exception as exc:
        log.error("queue_failed", error=type(exc).__name__)
        document.status = "failed"
        document.error = "Could not queue ingestion."
        session.commit()
    return document


@router.post("/documents", response_model=DocumentDetail, status_code=201)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> Document:
    data = file.file.read(request.app.state.settings.max_upload_bytes + 1)
    document = store_bytes(
        session,
        request.app.state.settings,
        workspace_id=principal.workspace.id,
        filename=file.filename or "document",
        data=data,
    )
    return _queue(request, session, document)


@router.get("/documents", response_model=DocumentList)
def list_documents(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> DocumentList:
    query = select(Document).where(Document.workspace_id == principal.workspace.id)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        session.scalars(query.order_by(Document.created_at.desc()).limit(limit).offset(offset)).all()
    )
    return DocumentList(items=[DocumentOut.model_validate(item) for item in items], total=int(total))


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> Document:
    return _require_document(session, principal, document_id)


@router.get("/documents/{document_id}/text", response_model=DocumentText)
def get_text(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> DocumentText:
    document = _require_document(session, principal, document_id)
    pages = []
    for index, page in enumerate(document.pages or [], start=1):
        number = page.get("page", index)
        pages.append(PageOut(page=int(str(number)), text=str(page.get("text", ""))))
    return DocumentText(document_id=document.id, language=document.language, pages=pages)


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> None:
    document = _require_document(session, principal, document_id)
    delete_document(session, document)


@router.post("/documents/{document_id}/reprocess", response_model=DocumentDetail)
def reprocess(
    document_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> Document:
    document = _require_document(session, principal, document_id)
    if not Path(document.storage_path).exists():
        # Hosts without a persistent disk drop uploads on restart. The text,
        # chunks and summary live in the database, so keep the document as it
        # is instead of letting a new run mark it failed.
        raise AppError(
            "source_missing",
            "The original file is no longer stored. Upload it again to reprocess it.",
            410,
        )
    if not requeue_document(session, document):
        raise AppError("already_processing", "This document is already being processed.", 409)
    return _queue(request, session, document)
