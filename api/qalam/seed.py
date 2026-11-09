from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from qalam.auth import bootstrap_account
from qalam.config import Settings
from qalam.llm.client import LLMClient
from qalam.logging import get_logger
from qalam.models import Document, Workspace
from qalam.services.ingest import process_document, store_bytes

log = get_logger("qalam.seed")


def write_pdf(path: Path, text: str) -> None:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    y = 64.0
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            y += 12
            continue
        line = ""
        for word in words:
            trial = word if not line else f"{line} {word}"
            if len(trial) > 90:
                if y > 780:
                    page = document.new_page()
                    y = 64
                page.insert_text((64, y), line, fontsize=11, fontname="helv")
                y += 15
                line = word
            else:
                line = trial
        if line:
            if y > 780:
                page = document.new_page()
                y = 64
            page.insert_text((64, y), line, fontsize=11, fontname="helv")
            y += 15
    document.save(path)
    document.close()


def write_docx(path: Path, text: str) -> None:
    from docx import Document

    document = Document()
    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)
    document.save(str(path))


def seed_if_empty(
    session: Session,
    settings: Settings,
    llm: LLMClient,
    *,
    force: bool = False,
) -> int:
    bootstrap_account(
        session,
        email=settings.bootstrap_email,
        name=settings.bootstrap_name,
        workspace_name=settings.bootstrap_workspace,
        api_key=settings.bootstrap_api_key,
    )
    workspace = session.scalar(select(Workspace).order_by(Workspace.created_at))
    if workspace is None:
        log.warning("seed_skipped", reason="no workspace")
        return 0
    existing = session.scalar(
        select(func.count()).select_from(Document).where(Document.workspace_id == workspace.id)
    )
    if existing and not force:
        return 0
    samples = Path(settings.samples_dir)
    specs = [
        ("lantern-memo.txt", "lantern-memo.pdf", "pdf"),
        ("atelier-fr.txt", "atelier-fr.docx", "docx"),
        ("warsha-ar.txt", "warsha-ar.txt", "txt"),
        ("invoice-en.txt", "invoice-en.txt", "txt"),
    ]
    created = 0
    for source_name, stored_name, kind in specs:
        source = samples / source_name
        if not source.exists():
            log.warning("seed_missing", file=source_name)
            continue
        text = source.read_text(encoding="utf-8")
        if kind == "pdf":
            target = Path(settings.storage_dir) / "_seed" / stored_name
            target.parent.mkdir(parents=True, exist_ok=True)
            write_pdf(target, text)
            data = target.read_bytes()
        elif kind == "docx":
            target = Path(settings.storage_dir) / "_seed" / stored_name
            target.parent.mkdir(parents=True, exist_ok=True)
            write_docx(target, text)
            data = target.read_bytes()
        else:
            data = text.encode("utf-8")
        document = store_bytes(
            session,
            settings,
            workspace_id=workspace.id,
            filename=stored_name,
            data=data,
        )
        process_document(session, document.id, settings, llm)
        created += 1
    log.info("seed_done", documents=created)
    return created
