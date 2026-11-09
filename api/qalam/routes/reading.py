import json
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from qalam.auth import Principal
from qalam.deps import get_principal, get_session
from qalam.errors import AppError
from qalam.models import Document, Extraction, Question, Translation
from qalam.routes.documents import _require_document
from qalam.schemas import (
    AnswerOut,
    CitationOut,
    ExtractIn,
    ExtractOut,
    QuestionIn,
    SummaryOut,
    TranslationIn,
    TranslationOut,
)
from qalam.services.ingest import joined_text
from qalam.services.reading import answer_question, extract_fields, retrieve, summarize_text, translate_text
from qalam.services.usage import record_usage

router = APIRouter(prefix="/v1", tags=["reading"])


def _release_connection(session: Session) -> None:
    """End the read transaction before a model call.

    Model calls can take tens of seconds across retries and provider fallback.
    Committing here returns the pooled connection, so slow LLM requests cannot
    exhaust the database pool. Loaded rows stay usable because the session does
    not expire them on commit.
    """

    session.commit()


def _ready(document: Document) -> None:
    if document.status != "ready":
        raise AppError("not_ready", "The document is not ready yet.", 409)


@router.get("/documents/{document_id}/summary", response_model=SummaryOut)
def get_summary(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> SummaryOut:
    document = _require_document(session, principal, document_id)
    if not document.summary_short or not document.summary_detailed:
        raise AppError("not_ready", "This document has no summary yet.", 409)
    return SummaryOut(
        short=document.summary_short,
        detailed=document.summary_detailed,
        provider=document.summary_provider,
        language=document.language,
    )


@router.post("/documents/{document_id}/summary", response_model=SummaryOut)
def regenerate_summary(
    document_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> SummaryOut:
    document = _require_document(session, principal, document_id)
    _ready(document)
    settings = request.app.state.settings
    text = joined_text(document, settings.llm_input_chars)
    _release_connection(session)
    summary = summarize_text(
        text,
        document.language or "unknown",
        request.app.state.llm,
        settings.llm_input_chars,
    )
    record_usage(session, principal.workspace.id, "summarize", summary.completion)
    document.summary_short = summary.short
    document.summary_detailed = summary.detailed
    document.summary_provider = summary.provider
    session.commit()
    return SummaryOut(
        short=summary.short,
        detailed=summary.detailed,
        provider=summary.provider,
        language=document.language,
    )


@router.post("/documents/{document_id}/translations", response_model=TranslationOut)
def create_translation(
    document_id: uuid.UUID,
    body: TranslationIn,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> TranslationOut:
    document = _require_document(session, principal, document_id)
    _ready(document)
    settings = request.app.state.settings
    text = joined_text(document, settings.llm_input_chars)
    _release_connection(session)
    result = translate_text(
        text,
        body.target_language,
        request.app.state.llm,
        settings.llm_input_chars,
    )
    record_usage(session, principal.workspace.id, "translate", result.completion)
    existing = session.scalar(
        select(Translation).where(
            Translation.document_id == document.id,
            Translation.target_language == body.target_language,
        )
    )
    if existing is None:
        existing = Translation(
            document_id=document.id,
            target_language=body.target_language,
            text=result.text,
            provider=result.provider,
        )
        session.add(existing)
    else:
        existing.text = result.text
        existing.provider = result.provider
    session.commit()
    return TranslationOut(
        language=result.language,
        direction=result.direction,
        paragraphs=result.paragraphs,
        text=result.text,
        provider=result.provider,
    )


@router.get("/documents/{document_id}/translations/{language}", response_model=TranslationOut)
def get_translation(
    document_id: uuid.UUID,
    language: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> TranslationOut:
    if language not in {"ar", "fr", "en"}:
        raise AppError("invalid_language", "Language must be ar, fr or en.", 422)
    document = _require_document(session, principal, document_id)
    row = session.scalar(
        select(Translation).where(
            Translation.document_id == document.id,
            Translation.target_language == language,
        )
    )
    if row is None:
        raise AppError("not_found", "Translation not found.", 404)
    paragraphs = [part.strip() for part in row.text.split("\n\n") if part.strip()]
    return TranslationOut(
        language=language,
        direction="rtl" if language == "ar" else "ltr",
        paragraphs=paragraphs,
        text=row.text,
        provider=row.provider,
    )


@router.get("/documents/{document_id}/questions", response_model=list[AnswerOut])
def list_questions(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[AnswerOut]:
    _require_document(session, principal, document_id)
    rows = session.scalars(
        select(Question)
        .where(
            Question.workspace_id == principal.workspace.id,
            Question.document_ids.contains([str(document_id)]),
        )
        .order_by(Question.created_at)
    ).all()
    return [_answer_out(row) for row in rows]


@router.post("/qa", response_model=AnswerOut)
def ask(
    body: QuestionIn,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> AnswerOut:
    documents = _load_ready(session, principal, body.document_ids)
    settings = request.app.state.settings
    hits = retrieve(
        session,
        settings,
        workspace_id=principal.workspace.id,
        document_ids=[document.id for document in documents],
        question=body.question,
        top_k=body.top_k,
    )
    if not hits:
        raise AppError("no_context", "Those documents have no indexed text yet.", 409)
    _release_connection(session)
    result = answer_question(body.question, hits, request.app.state.llm)
    record_usage(session, principal.workspace.id, "qa", result.completion)
    row = Question(
        workspace_id=principal.workspace.id,
        document_ids=[str(document.id) for document in documents],
        question=body.question.strip(),
        answer=result.answer,
        citations=result.citations,
        provider=result.provider,
    )
    session.add(row)
    session.commit()
    return _answer_out(row)


@router.post("/extract", response_model=ExtractOut)
def extract(
    body: ExtractIn,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> ExtractOut:
    encoded = json.dumps(body.json_schema)
    if len(encoded) > 20_000:
        raise AppError("invalid_schema", "The schema is too large.", 422)
    documents = _load_ready(session, principal, body.document_ids)
    settings = request.app.state.settings
    parts = [
        f"# {document.filename}\n{joined_text(document, settings.llm_input_chars)}" for document in documents
    ]
    _release_connection(session)
    result, completion = extract_fields(
        "\n\n".join(parts),
        body.json_schema,
        request.app.state.llm,
        settings.llm_input_chars,
    )
    record_usage(session, principal.workspace.id, "extract", completion)
    row = Extraction(
        workspace_id=principal.workspace.id,
        document_ids=[str(document.id) for document in documents],
        json_schema=body.json_schema,
        result=result,
        provider=completion.provider,
    )
    session.add(row)
    session.commit()
    return ExtractOut(id=row.id, result=result, provider=completion.provider, created_at=row.created_at)


def _load_ready(
    session: Session,
    principal: Principal,
    document_ids: list[uuid.UUID],
) -> list[Document]:
    documents: list[Document] = []
    for document_id in document_ids:
        document = _require_document(session, principal, document_id)
        _ready(document)
        documents.append(document)
    return documents


def _answer_out(row: Question) -> AnswerOut:
    citations = [CitationOut.model_validate(item) for item in row.citations]
    return AnswerOut(
        id=row.id,
        question=row.question,
        answer=row.answer,
        citations=citations,
        provider=row.provider,
        created_at=row.created_at,
    )
