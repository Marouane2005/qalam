import time

from qalam.config import Settings
from qalam.llm.breaker import CircuitBreaker
from qalam.llm.mock import MockProvider
from qalam.llm.providers import OpenAICompatibleProvider
from qalam.llm.types import Completion, LLMUnavailable, Message, ProviderError
from qalam.logging import get_logger
from qalam.metrics import LLM_LATENCY, LLM_REQUESTS, LLM_TOKENS

log = get_logger("qalam.llm")

_REMOTE = (
    (
        "inception",
        "inception_api_key",
        "inception_base_url",
        "inception_model",
        "inception_timeout_s",
        "inception_retries",
    ),
    (
        "nvidia",
        "nvidia_api_key",
        "nvidia_base_url",
        "nvidia_model",
        "nvidia_timeout_s",
        "nvidia_retries",
    ),
    (
        "exaone",
        "exaone_api_key",
        "exaone_base_url",
        "exaone_model",
        "exaone_timeout_s",
        "exaone_retries",
    ),
    (
        "openrouter",
        "openrouter_api_key",
        "openrouter_base_url",
        "openrouter_model",
        "openrouter_timeout_s",
        "openrouter_retries",
    ),
)


class LLMClient:
    def __init__(
        self,
        providers: list[MockProvider | OpenAICompatibleProvider],
        *,
        threshold: int,
        cooldown_s: float,
    ) -> None:
        self.providers = providers
        self.breakers = {provider.name: CircuitBreaker(threshold, cooldown_s) for provider in providers}

    @property
    def provider_names(self) -> list[str]:
        return [provider.name for provider in self.providers]

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int,
        temperature: float = 0.7,
        operation: str,
    ) -> Completion:
        failures: list[ProviderError] = []
        for provider in self.providers:
            breaker = self.breakers[provider.name]
            if not breaker.allow():
                log.info("llm_circuit_open", provider=provider.name, operation=operation)
                continue
            started = time.perf_counter()
            try:
                result = provider.complete(messages, max_tokens=max_tokens, temperature=temperature)
            except ProviderError as exc:
                breaker.record_failure()
                failures.append(exc)
                LLM_REQUESTS.labels(provider.name, operation, "error").inc()
                log.warning(
                    "llm_provider_failed",
                    provider=provider.name,
                    operation=operation,
                    status=exc.status,
                )
                continue
            breaker.record_success()
            if result.latency_ms <= 0:
                result.latency_ms = (time.perf_counter() - started) * 1000
            LLM_REQUESTS.labels(provider.name, operation, "ok").inc()
            LLM_LATENCY.labels(provider.name, operation).observe(result.latency_ms / 1000)
            LLM_TOKENS.labels(provider.name, "prompt").inc(result.prompt_tokens)
            LLM_TOKENS.labels(provider.name, "completion").inc(result.completion_tokens)
            log.info(
                "llm_call",
                provider=result.provider,
                model=result.model,
                operation=operation,
                latency_ms=round(result.latency_ms, 1),
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
            return result
        LLM_REQUESTS.labels("none", operation, "error").inc()
        raise LLMUnavailable(failures)


def build_providers(settings: Settings) -> list[MockProvider | OpenAICompatibleProvider]:
    specs = {item[0]: item for item in _REMOTE}
    wanted = [name.strip() for name in settings.llm_chain.split(",") if name.strip()]
    providers: list[MockProvider | OpenAICompatibleProvider] = []
    for name in wanted:
        if name == "mock":
            providers.append(MockProvider())
            continue
        spec = specs.get(name)
        if spec is None:
            log.warning("llm_unknown_provider", provider=name)
            continue
        _name, key_attr, url_attr, model_attr, timeout_attr, retries_attr = spec
        api_key = getattr(settings, key_attr)
        if not api_key:
            continue
        timeout = getattr(settings, timeout_attr)
        retries = getattr(settings, retries_attr)
        providers.append(
            OpenAICompatibleProvider(
                name,
                base_url=getattr(settings, url_attr),
                api_key=api_key,
                model=getattr(settings, model_attr),
                timeout_s=settings.llm_timeout_s if timeout is None else timeout,
                retries=settings.llm_retries if retries is None else retries,
                backoff_s=settings.llm_retry_backoff_s,
            )
        )
    if not providers:
        log.warning("llm_chain_empty")
        providers.append(MockProvider())
    return providers


def build_client(settings: Settings) -> LLMClient:
    return LLMClient(
        build_providers(settings),
        threshold=settings.llm_breaker_threshold,
        cooldown_s=settings.llm_breaker_cooldown_s,
    )
