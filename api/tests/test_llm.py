import json
import logging

import httpx
import pytest

from qalam.config import Settings
from qalam.llm.breaker import CircuitBreaker
from qalam.llm.client import LLMClient, build_providers
from qalam.llm.mock import MockProvider
from qalam.llm.parsing import parse_model_json
from qalam.llm.providers import OpenAICompatibleProvider
from qalam.llm.types import Completion, LLMUnavailable, Message, ProviderError
from qalam.logging import configure_logging, redact, sanitize
from qalam.services.reading import extract_fields, summarize_text, translate_text, translation_max_tokens


class Scripted:
    def __init__(self, name: str, results: list[Completion | Exception]) -> None:
        self.name = name
        self.model = "script"
        self.results = list(results)
        self.calls = 0

    def complete(self, messages: list[Message], *, max_tokens: int, temperature: float) -> Completion:
        self.calls += 1
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _completion(text: str, provider: str = "scripted") -> Completion:
    return Completion(
        text=text,
        provider=provider,
        model="script",
        latency_ms=3,
        prompt_tokens=4,
        completion_tokens=2,
    )


def test_circuit_opens_and_half_opens() -> None:
    breaker = CircuitBreaker(threshold=2, cooldown_s=0)
    assert breaker.allow()
    breaker.record_failure()
    assert breaker.state == "closed"
    breaker.record_failure()
    assert breaker.state == "open"
    assert breaker.allow()
    assert breaker.state == "half_open"
    breaker.record_success()
    assert breaker.state == "closed"


def test_client_falls_through_an_open_circuit() -> None:
    failing = Scripted("primary", [ProviderError("primary", "down", retryable=True)] * 4)
    backup = Scripted(
        "backup",
        [_completion("ok", "backup"), _completion("ok", "backup"), _completion("ok", "backup")],
    )
    client = LLMClient([failing, backup], threshold=2, cooldown_s=60)  # type: ignore[list-item]
    first = client.complete([Message("user", "hi")], max_tokens=20, operation="qa")
    second = client.complete([Message("user", "hi")], max_tokens=20, operation="qa")
    third = client.complete([Message("user", "hi")], max_tokens=20, operation="qa")
    assert first.provider == "backup"
    assert second.provider == "backup"
    assert third.provider == "backup"
    assert failing.calls == 2
    assert backup.calls == 3


def test_client_raises_when_every_provider_fails() -> None:
    failing = Scripted("primary", [ProviderError("primary", "down")])
    client = LLMClient([failing], threshold=3, cooldown_s=10)  # type: ignore[list-item]
    with pytest.raises(LLMUnavailable):
        client.complete([Message("user", "hi")], max_tokens=10, operation="qa")


def test_chain_skips_providers_without_keys() -> None:
    empty = Settings(llm_chain="inception,nvidia,exaone,openrouter,mock", inception_api_key="")
    assert [provider.name for provider in build_providers(empty)] == ["mock"]
    configured = Settings(llm_chain="inception,mock", inception_api_key="sk-inceptiontestkey")
    providers = build_providers(configured)
    assert [provider.name for provider in providers] == ["inception", "mock"]
    assert "sk-inceptiontestkey" not in repr(providers[0])


def test_chain_falls_back_to_mock_when_nothing_is_configured() -> None:
    settings = Settings(llm_chain="inception,nvidia")
    assert [provider.name for provider in build_providers(settings)] == ["mock"]


def test_http_provider_retries_and_hides_secrets() -> None:
    secret = "sk-testsecret1234"
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.headers["Authorization"] == f"Bearer {secret}"
        if calls["n"] == 1:
            return httpx.Response(503, text=json.dumps({"error": secret}))
        return httpx.Response(
            200,
            json={
                "model": "meta/llama-3.3-70b-instruct",
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            },
        )

    provider = OpenAICompatibleProvider(
        "nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=secret,
        model="meta/llama-3.3-70b-instruct",
        timeout_s=2,
        retries=1,
        backoff_s=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = provider.complete([Message("user", "hi")], max_tokens=16, temperature=0.7)
    assert result.text == "hello"
    assert result.prompt_tokens == 5
    assert calls["n"] == 2
    assert secret not in repr(provider)


def test_http_provider_does_not_retry_a_client_error_and_redacts_the_body() -> None:
    secret = "sk-testsecret1234"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=json.dumps({"error": secret}))

    provider = OpenAICompatibleProvider(
        "openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=secret,
        model="openrouter/free",
        timeout_s=1,
        retries=3,
        backoff_s=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ProviderError) as caught:
        provider.complete([Message("user", "hi")], max_tokens=8, temperature=0.7)
    assert secret not in str(caught.value)
    assert "[redacted]" in str(caught.value)
    assert caught.value.status == 401


def test_http_provider_retries_timeouts() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.TimeoutException("slow")

    provider = OpenAICompatibleProvider(
        "exaone",
        base_url="https://api.friendli.ai/serverless/v1",
        api_key="exaone-test-key",
        model="LGAI-EXAONE/EXAONE-4.0.1-32B",
        timeout_s=1,
        retries=1,
        backoff_s=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ProviderError):
        provider.complete([Message("user", "hi")], max_tokens=8, temperature=0.7)
    assert calls["n"] == 2


def test_logs_redact_keys(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("INFO")
    caplog.set_level(logging.INFO)
    event = redact(
        {
            "event": "auth",
            "authorization": "Bearer qlm_supersecretvalue",
            "note": "saw sk-anothersecretvalue in the body",
        }
    )
    rendered = json.dumps(event)
    assert "supersecretvalue" not in rendered
    assert "anothersecretvalue" not in rendered
    assert sanitize("Bearer qlm_supersecretvalue") == "Bearer [redacted]"


def test_parse_json_with_fences_and_surrounding_prose() -> None:
    assert parse_model_json('```json\n{"short": "Hi"}\n```') == {"short": "Hi"}
    assert parse_model_json('Sure.\n{"short": "Hi"}\nThanks.') == {"short": "Hi"}
    assert parse_model_json("Here: [1, 2]") == [1, 2]
    with pytest.raises(json.JSONDecodeError):
        parse_model_json("no json here")


def test_mock_summary_translation_and_extraction() -> None:
    client = LLMClient([MockProvider()], threshold=2, cooldown_s=5)
    text = "Alpha is the first fact. Beta is the second fact. Gamma closes the note."
    summary = summarize_text(text, "en", client, 4000)
    assert "Alpha" in summary.short
    assert "Gamma" in summary.detailed
    translated = translate_text("First paragraph.\n\nSecond paragraph.", "ar", client, 4000)
    assert translated.paragraphs == ["First paragraph.", "Second paragraph."]
    assert translated.direction == "rtl"
    schema = {
        "type": "object",
        "required": ["invoice_number", "total"],
        "properties": {
            "invoice_number": {"type": "string"},
            "date": {"type": "string"},
            "seller": {"type": "string"},
            "total": {"type": "string"},
        },
    }
    invoice = "Invoice: INV-1042\nDate: 2026-03-02\nSeller: Northwind Studio\nTotal: 900.00 EUR\n"
    result, completion = extract_fields(invoice, schema, client, 4000)
    assert result["invoice_number"] == "INV-1042"
    assert result["seller"] == "Northwind Studio"
    assert "900.00" in result["total"]
    assert completion.provider == "mock"


def test_extraction_retries_invalid_schema_output() -> None:
    schema = {
        "type": "object",
        "required": ["invoice_number"],
        "properties": {"invoice_number": {"type": "string"}},
    }
    scripted = Scripted(
        "scripted",
        [
            _completion('{"invoice_number": 12}'),
            _completion('{"invoice_number": "INV-9"}'),
        ],
    )
    client = LLMClient([scripted], threshold=3, cooldown_s=5)  # type: ignore[list-item]
    result, _completion_done = extract_fields("Invoice: INV-9", schema, client, 1000)
    assert result["invoice_number"] == "INV-9"
    assert scripted.calls == 2


def test_translation_max_tokens_leaves_room_for_expansion() -> None:
    short = ["Total due: 1140 MAD"]
    assert translation_max_tokens(short) >= 1600
    long = ["x" * 2000]
    assert translation_max_tokens(long) == 4000

