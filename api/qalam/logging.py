import logging
import re
from collections.abc import MutableMapping
from typing import Any

import structlog

# Bearer tokens, Qalam keys, and common vendor key prefixes.
_SECRET = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"
    r"|(?:qlm_|sk-|nvapi-)[A-Za-z0-9_\-]{8,}"
)
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
    "bootstrap_api_key",
    "key",
    "key_hash",
}


def sanitize(value: str) -> str:
    return _SECRET.sub(lambda match: (match.group(1) or "") + "[redacted]", value)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[Any, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return sanitize(value)
    return value


def _redact_processor(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    redacted = redact(event_dict)
    if isinstance(redacted, dict):
        return redacted
    return {"event": redacted}


def configure_logging(level: str) -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
