import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from qalam.errors import IngestError

_LETTERS = re.compile(r"[A-Za-z\u0600-\u06FF]")


@dataclass(frozen=True)
class PageText:
    number: int
    text: str


def usable_text(text: str) -> bool:
    return len(_LETTERS.findall(text)) >= 20


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1256"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def ocr_image(image: Image.Image) -> str:
    import pytesseract

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    try:
        return pytesseract.image_to_string(image, lang="ara+fra+eng")
    except pytesseract.TesseractNotFoundError as exc:
        raise IngestError("Tesseract is not installed on this host.") from exc
    except pytesseract.TesseractError as exc:
        raise IngestError("OCR failed for this image.") from exc


def extract_docx(path: Path) -> list[PageText]:
    from docx import Document

    document = Document(str(path))
    pages: list[list[str]] = [[]]
    for paragraph in document.paragraphs:
        xml = paragraph._p.xml
        if pages[-1] and ('w:type="page"' in xml or "lastRenderedPageBreak" in xml):
            pages.append([])
        if paragraph.text.strip():
            pages[-1].append(paragraph.text.strip())
    rendered = [PageText(index, "\n\n".join(parts).strip()) for index, parts in enumerate(pages, start=1)]
    return [page for page in rendered if page.text] or [PageText(1, "")]


def extract_pdf(path: Path) -> list[PageText]:
    import pymupdf

    document: Any = pymupdf.open(path)
    pages: list[PageText] = []
    try:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text") or ""
            if usable_text(text):
                pages.append(PageText(index, text.strip()))
                continue
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            pages.append(PageText(index, ocr_image(image).strip()))
    finally:
        document.close()
    return pages


def extract_pages(path: Path, media_type: str) -> list[PageText]:
    suffix = path.suffix.lower()
    if media_type == "text/plain" or suffix == ".txt":
        return [PageText(1, read_text(path).strip())]
    if suffix == ".docx" or "wordprocessingml" in media_type:
        return extract_docx(path)
    if media_type == "application/pdf" or suffix == ".pdf":
        return extract_pdf(path)
    if media_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
        with Image.open(path) as image:
            return [PageText(1, ocr_image(image).strip())]
    raise IngestError("This file type is not supported.")
