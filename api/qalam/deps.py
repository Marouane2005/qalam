from collections.abc import Iterator

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from qalam.auth import Principal, lookup_principal
from qalam.config import Settings
from qalam.errors import AppError
from qalam.ratelimit import RateLimiter


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_principal(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> Principal:
    raw = request.headers.get("x-api-key", "").strip()
    if not raw:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            raw = header[7:].strip()
    principal = lookup_principal(session, raw)
    if principal is None:
        raise AppError("unauthorized", "A valid API key is required.", 401)
    settings: Settings = request.app.state.settings
    allowed, remaining = RateLimiter(request.app.state.redis, settings.rate_limit_per_minute).hit(
        str(principal.api_key.id)
    )
    response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    if not allowed:
        raise AppError("rate_limited", "Too many requests.", 429, headers={"Retry-After": "60"})
    return principal
