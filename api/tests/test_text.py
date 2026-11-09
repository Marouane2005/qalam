from pathlib import Path

import pymupdf
import pytest
from docx import Document
from PIL import Image, ImageDraw

from qalam.config import Settings
from qalam.text.chunk import chunk_pages, split_paragraphs
from qalam.text.embed import cosine, embed_texts, hash_embed
from qalam.text.extract import extract_pages, usable_text
from qalam.text.language import detect_language, direction_for


def test_language_detection() -> None:
    english = (
        "The reading room closes at 18:00 on Fridays and opens again on Saturday morning. "
        "Please tell the evening desk before you leave the building."
    )
    french = (
        "L'atelier se réunit chaque mardi dans la salle des cartes et la cotisation "
        "annuelle est de quarante euros pour l'année en cours."
    )
    arabic = "تُقام الورشة يوم السبت في قاعة الطابق الثاني ويشمل الرسم الأوراق والشاي للجيران."
    assert detect_language(english) == "en"
    assert detect_language(french) == "fr"
    assert detect_language(arabic) == "ar"
    assert detect_language("12345 ---") == "unknown"
    assert detect_language("   ") == "unknown"
    assert direction_for("ar") == "rtl"
    assert direction_for("fr") == "ltr"


def test_chunking_overlaps_and_finishes() -> None:
    text = "alpha " * 5000
    drafts = chunk_pages([(2, text)], size=300, overlap=40)
    assert len(drafts) > 10
    assert drafts[0].page == 2
    assert drafts[0].char_end > drafts[1].char_start
    assert "alpha" in drafts[-1].text
    assert chunk_pages([(1, "   ")], size=100, overlap=10) == []
    assert split_paragraphs("One.\n\n\nTwo.") == ["One.", "Two."]


def test_hash_embeddings_rank_related_text() -> None:
    settings = Settings(embedding_backend="hash", llm_chain="mock")
    query, close, far = embed_texts(
        [
            "reading room friday hours",
            "the reading room closes at 18:00 on fridays",
            "the cafeteria serves lentil soup on monday",
        ],
        settings,
    )
    assert len(query) == 384
    assert cosine(query, close) > cosine(query, far)
    single = hash_embed("qalam")
    assert abs(sum(value * value for value in single) - 1) < 1e-6


def test_plain_text_docx_and_pdf(tmp_path: Path) -> None:
    text_path = tmp_path / "note.txt"
    text_path.write_text("Hello from Qalam.\n\nA second paragraph.", encoding="utf-8")
    pages = extract_pages(text_path, "text/plain")
    assert "Hello from Qalam" in pages[0].text

    docx_path = tmp_path / "note.docx"
    document = Document()
    document.add_paragraph("Bonjour de Qalam, ceci est un fichier word.")
    document.save(docx_path)
    media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    docx_pages = extract_pages(docx_path, media)
    assert "Bonjour" in docx_pages[0].text

    pdf_path = tmp_path / "note.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "The reading room closes at 18:00 on Fridays according to this PDF.")
    pdf.save(pdf_path)
    pdf.close()
    pdf_pages = extract_pages(pdf_path, "application/pdf")
    assert usable_text(pdf_pages[0].text)
    assert "18:00" in pdf_pages[0].text


def test_ocr_image_when_tesseract_is_installed(tmp_path: Path) -> None:
    pytest.importorskip("pytesseract")
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("tesseract is not installed")
    image_path = tmp_path / "scan.png"
    image = Image.new("RGB", (640, 160), "white")
    draw = ImageDraw.Draw(image)
    font = None
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if font_path.exists():
        from PIL import ImageFont

        font = ImageFont.truetype(str(font_path), 36)
    draw.text((20, 50), "Qalam invoice 42", fill="black", font=font)
    image.save(image_path)
    pages = extract_pages(image_path, "image/png")
    assert "42" in pages[0].text
