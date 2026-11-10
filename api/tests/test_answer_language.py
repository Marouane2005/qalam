import json
import uuid
from typing import Any

import pytest

from qalam.errors import ModelOutputError
from qalam.llm.types import Completion, Message
from qalam.services.reading import Hit, answer_language, answer_question


class Replies:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.prompts: list[list[Message]] = []

    def complete(self, messages: list[Message], **_kwargs: Any) -> Completion:
        self.prompts.append(list(messages))
        text = json.dumps({"answer": self.answers.pop(0), "citation_indexes": [0]}, ensure_ascii=False)
        return Completion(
            text=text, provider="fake", model="fake", latency_ms=1, prompt_tokens=1, completion_tokens=1
        )


HITS = [Hit(uuid.uuid4(), uuid.uuid4(), "note.txt", 1, "المكتبة تغلق يوم الأحد عند الظهر.")]


def test_answer_language_follows_the_question() -> None:
    assert answer_language("When does the library close on Sunday?") == "English"
    assert answer_language("متى تغلق المكتبة يوم الأحد؟") == "Arabic"


def test_the_prompt_names_the_question_language() -> None:
    llm = Replies(["It closes at noon on Sunday."])
    answer_question("When does the library close on Sunday?", HITS, llm)  # type: ignore[arg-type]
    assert "Answer language: English" in llm.prompts[0][1].content


def test_a_reply_in_chinese_is_retried_in_the_question_language() -> None:
    llm = Replies(["图书馆周日中午关门。", "It closes at noon on Sunday."])
    result = answer_question("When does the library close on Sunday?", HITS, llm)  # type: ignore[arg-type]
    assert result.answer == "It closes at noon on Sunday."
    assert "English" in llm.prompts[1][-1].content


def test_two_drifted_replies_raise() -> None:
    llm = Replies(["图书馆周日中午关门。", "周日中午。"])
    with pytest.raises(ModelOutputError):
        answer_question("When does the library close on Sunday?", HITS, llm)  # type: ignore[arg-type]
