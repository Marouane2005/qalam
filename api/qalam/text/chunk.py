from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkDraft:
    page: int
    position: int
    text: str
    char_start: int
    char_end: int


def chunk_pages(
    pages: list[tuple[int, str]],
    size: int,
    overlap: int,
) -> list[ChunkDraft]:
    if size < 1:
        raise ValueError("chunk size must be positive")
    overlap = max(0, min(overlap, size - 1))
    drafts: list[ChunkDraft] = []
    position = 0
    for number, raw in pages:
        text = raw.strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                window = text[start:end]
                break_at = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(" "))
                if break_at >= size // 2:
                    end = start + break_at
            piece = text[start:end].strip()
            if piece:
                drafts.append(
                    ChunkDraft(
                        page=number,
                        position=position,
                        text=piece,
                        char_start=start,
                        char_end=end,
                    )
                )
                position += 1
            if end >= len(text):
                break
            next_start = end - overlap
            if next_start <= start:
                next_start = end
            start = next_start
    return drafts


def split_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in text.split("\n\n")]
    paragraphs = [part for part in parts if part]
    if paragraphs:
        return paragraphs
    stripped = text.strip()
    return [stripped] if stripped else []
