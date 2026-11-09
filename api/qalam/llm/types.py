from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass
class Completion:
    text: str
    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int


class ProviderError(Exception):
    def __init__(
        self,
        provider: str,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status = status
        self.retryable = retryable


class LLMUnavailable(Exception):
    def __init__(self, failures: list[ProviderError]) -> None:
        self.failures = failures
        names = ", ".join(item.provider for item in failures) or "none"
        super().__init__(f"No provider succeeded ({names})")
