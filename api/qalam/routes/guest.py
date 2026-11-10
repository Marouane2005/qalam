from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from qalam.auth import create_guest
from qalam.deps import get_session
from qalam.errors import AppError
from qalam.ratelimit import RateLimiter
from qalam.schemas import GuestCreated, UserOut, WorkspaceOut

router = APIRouter(prefix="/v1", tags=["guest"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


@router.post("/guest", response_model=GuestCreated, status_code=201)
def start_guest(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> GuestCreated:
    settings = request.app.state.settings
    if not settings.guest_access:
        raise AppError("guest_disabled", "Guest access is not enabled.", 404)

    limit = settings.guest_signups_per_minute
    allowed, remaining = RateLimiter(request.app.state.redis, limit).hit(f"guest:{_client_ip(request)}")
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    if not allowed:
        raise AppError("rate_limited", "Too many requests.", 429, headers={"Retry-After": "60"})

    user, workspace, raw = create_guest(session)
    return GuestCreated(
        api_key=raw,
        workspace=WorkspaceOut.model_validate(workspace),
        user=UserOut.model_validate(user),
    )
