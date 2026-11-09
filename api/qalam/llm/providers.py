import json
import time

import httpx

from qalam.llm.parsing import estimate_tokens
from qalam.llm.types import Completion, Message, ProviderError
from qalam.logging import sanitize

_RETRYABLE = {408, 409, 429, 500, 502, 503, 504}


class OpenAICompatibleProvider:
    """Chat completions against any server that speaks the OpenAI JSON shape."""

    def __init__(
        self,
        name: str,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float,
        retries: int,
        backoff_s: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.retries = max(0, retries)
        self.backoff_s = max(0.0, backoff_s)
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_s))
        self._owns_client = client is None

    def __repr__(self) -> str:
        return (
            f"OpenAICompatibleProvider(name={self.name!r}, model={self.model!r}, base_url={self.base_url!r})"
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def complete(self, messages: list[Message], *, max_tokens: int, temperature: float) -> Completion:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        last: ProviderError | None = None
        for attempt in range(self.retries + 1):
            started = time.perf_counter()
            try:
                response = self._client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                last = ProviderError(self.name, "timed out", retryable=True)
            except httpx.HTTPError:
                last = ProviderError(self.name, "connection failed", retryable=True)
            else:
                if response.status_code in _RETRYABLE:
                    last = ProviderError(
                        self.name,
                        f"status {response.status_code}: {sanitize(response.text)[:240]}",
                        status=response.status_code,
                        retryable=True,
                    )
                elif response.status_code >= 400:
                    raise ProviderError(
                        self.name,
                        f"status {response.status_code}: {sanitize(response.text)[:240]}",
                        status=response.status_code,
                        retryable=False,
                    )
                else:
                    return self._parse(response, messages, (time.perf_counter() - started) * 1000)
            if attempt < self.retries and self.backoff_s:
                time.sleep(self.backoff_s * (2**attempt))
        if last is None:
            raise ProviderError(self.name, "no response", retryable=True)
        raise last

    def _parse(self, response: httpx.Response, messages: list[Message], latency_ms: float) -> Completion:
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise ProviderError(self.name, "invalid JSON response") from None
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise ProviderError(self.name, "missing completion text") from None
        usage = data.get("usage") if isinstance(data, dict) else None
        if not isinstance(usage, dict):
            usage = {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        if prompt_tokens <= 0:
            prompt_tokens = estimate_tokens("\n".join(message.content for message in messages))
        if completion_tokens <= 0:
            completion_tokens = estimate_tokens(str(text))
        return Completion(
            text=str(text),
            provider=self.name,
            model=str(data.get("model") or self.model),
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
