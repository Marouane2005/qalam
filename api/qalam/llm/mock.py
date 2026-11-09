import json
import re
import time
from typing import Any

from qalam.llm.parsing import estimate_tokens
from qalam.llm.types import Completion, Message

_LABELS: dict[str, list[str]] = {
    "invoice_number": ["invoice number", "invoice_number", "invoice", "facture", "رقم الفاتورة"],
    "date": ["date", "dated", "تاريخ"],
    "seller": ["seller", "from", "vendeur", "البائع"],
    "buyer": ["buyer", "bill to", "client", "acheteur"],
    "total": ["total", "amount due", "montant", "المجموع", "الرسم"],
    "currency": ["currency", "devise"],
    "subject": ["subject", "objet", "موضوع"],
    "place": ["place", "lieu", "المكان"],
    "description": ["description"],
}


def _section(text: str, label: str) -> str:
    marker = label if label.endswith(":") else f"{label}:"
    index = text.find(marker)
    if index < 0:
        return ""
    return text[index + len(marker) :].strip()


def _sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        parts = re.split(r"(?<=[\.!\?؟])\s+", block.strip())
        sentences.extend(part.strip() for part in parts if part.strip())
    return sentences


_STOP = {
    "the",
    "a",
    "an",
    "of",
    "on",
    "in",
    "at",
    "to",
    "and",
    "or",
    "for",
    "is",
    "are",
    "does",
    "do",
    "when",
    "what",
    "where",
    "who",
    "how",
    "this",
    "that",
    "with",
    "from",
    "le",
    "la",
    "les",
    "de",
    "des",
    "du",
    "un",
    "une",
    "et",
    "est",
    "que",
    "qui",
    "dans",
    "au",
    "aux",
    "en",
    "pour",
    "sur",
    "ce",
    "cette",
    "par",
    "pas",
    "ne",
    "nous",
    "vous",
    "في",
    "من",
    "إلى",
    "على",
    "عن",
    "ما",
    "هل",
    "هذا",
    "هذه",
    "ذلك",
}


def _tokens(text: str) -> set[str]:
    found = {token.lower() for token in re.findall(r"[\w\u0600-\u06FF]+", text)}
    return {token for token in found if token not in _STOP and (len(token) >= 3 or token.isdigit())}


def _find_labeled(text: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = re.compile(rf"(?im)(?:^|\n)\s*{re.escape(label)}\s*(?:[:：]|is|est)\s*([^\n]+)")
        match = pattern.search(text)
        if match:
            return match.group(1).strip(" .")
    for label in labels:
        pattern = re.compile(rf"(?i){re.escape(label)}\s*(?:[:：]|is|est)\s*([^\n,;]+)")
        match = pattern.search(text)
        if match:
            return match.group(1).strip(" .")
    return None


def _string_value(name: str, text: str) -> str:
    labels = _LABELS.get(name, [name.replace("_", " "), name])
    found = _find_labeled(text, labels)
    if found:
        return found[:300]
    if "date" in name:
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if match:
            return match.group(0)
    if "invoice" in name:
        match = re.search(r"\b[A-Z]{2,}-\d+\b", text)
        if match:
            return match.group(0)
    if "email" in name:
        match = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+", text)
        if match:
            return match.group(0)
    if name in {"total", "amount"}:
        match = re.search(r"\b\d+(?:[.,]\d{2})?\b", text)
        if match:
            return match.group(0)
    return ""


def _fill_named(name: str, schema: dict[str, Any], text: str) -> Any:
    kind = schema.get("type", "string")
    if kind == "object":
        properties = schema.get("properties") or {}
        return {
            child_name: _fill_named(
                child_name,
                child if isinstance(child, dict) else {"type": "string"},
                text,
            )
            for child_name, child in properties.items()
        }
    if kind == "array":
        return []
    if kind in {"integer", "number"}:
        raw = _string_value(name, text)
        match = re.search(r"-?\d+(?:[.,]\d+)?", raw)
        if not match:
            return 0
        number = float(match.group(0).replace(",", "."))
        return int(number) if kind == "integer" else number
    if kind == "boolean":
        return bool(re.search(r"\b(yes|true|oui)\b", text.lower()))
    return _string_value(name, text)


def _extract(user: str) -> str:
    schema_raw = _section(user, "Schema:")
    document = _section(user, "Document:")
    try:
        schema = json.loads(schema_raw.split("\nDocument:")[0])
    except json.JSONDecodeError:
        schema = {"type": "object", "properties": {}}
    properties = schema.get("properties") or {}
    result = {
        name: _fill_named(name, child if isinstance(child, dict) else {"type": "string"}, document)
        for name, child in properties.items()
    }
    return json.dumps(result, ensure_ascii=False)


def _summarize(user: str) -> str:
    document = _section(user, "Document:")
    sentences = _sentences(document)
    short = " ".join(sentences[:2])[:500] or document[:280]
    detailed = " ".join(sentences[:8])[:1600] or document[:1200]
    return json.dumps({"short": short, "detailed": detailed}, ensure_ascii=False)


def _translate(user: str) -> str:
    raw = _section(user, "Paragraphs:")
    try:
        paragraphs = json.loads(raw)
    except json.JSONDecodeError:
        paragraphs = [raw]
    if not isinstance(paragraphs, list):
        paragraphs = [str(paragraphs)]
    return json.dumps({"paragraphs": [str(item) for item in paragraphs]}, ensure_ascii=False)


def _answer(user: str) -> str:
    question = ""
    for line in user.splitlines():
        if line.startswith("Question:"):
            question = line[len("Question:") :].strip()
            break
    raw = _section(user, "Context:")
    try:
        contexts = json.loads(raw)
    except json.JSONDecodeError:
        contexts = []
    if not isinstance(contexts, list) or not contexts:
        return json.dumps({"answer": "I could not find that in the documents.", "citation_indexes": []})
    wanted = _tokens(question)
    scored: list[tuple[int, int]] = []
    for index, item in enumerate(contexts):
        if not isinstance(item, dict):
            continue
        overlap = len(wanted & _tokens(str(item.get("text", ""))))
        scored.append((overlap, index))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best = [index for overlap, index in scored if overlap > 0][:3] or [scored[0][1]]
    text = str(contexts[best[0]].get("text", "")).strip()
    sentences = _sentences(text) or ([text] if text else [])
    ranked = sorted(
        ((len(wanted & _tokens(sentence)), sentence) for sentence in sentences),
        key=lambda item: item[0],
        reverse=True,
    )
    picked = [sentence for score, sentence in ranked if score > 0][:2] or sentences[:2]
    answer = " ".join(picked) if picked else text[:400]
    return json.dumps({"answer": answer, "citation_indexes": best}, ensure_ascii=False)


class MockProvider:
    """Deterministic stand-in used in tests and when no provider key is configured.

    Summaries are extractive. Translations keep the source paragraphs so the
    pipeline can be exercised offline. Question answering picks the context
    passage with the most overlapping words. Field extraction looks for labels.
    """

    name = "mock"
    model = "mock"

    def __repr__(self) -> str:
        return "MockProvider()"

    def complete(self, messages: list[Message], *, max_tokens: int, temperature: float) -> Completion:
        started = time.perf_counter()
        system = next((message.content for message in messages if message.role == "system"), "")
        user = ""
        for message in reversed(messages):
            if message.role != "user":
                continue
            if any(marker in message.content for marker in ("Document:", "Paragraphs:", "Context:")):
                user = message.content
                break
        if not user and messages:
            user = messages[-1].content
        if "QALAM_TASK: summarize" in system:
            text = _summarize(user)
        elif "QALAM_TASK: translate" in system:
            text = _translate(user)
        elif "QALAM_TASK: answer" in system:
            text = _answer(user)
        elif "QALAM_TASK: extract" in system:
            text = _extract(user)
        else:
            text = json.dumps({"text": user[: max_tokens * 4]})
        prompt = "\n".join(message.content for message in messages)
        return Completion(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=(time.perf_counter() - started) * 1000,
            prompt_tokens=estimate_tokens(prompt),
            completion_tokens=estimate_tokens(text),
        )
