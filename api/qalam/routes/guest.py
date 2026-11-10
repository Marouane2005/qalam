from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from qalam.auth import create_guest
from qalam.deps import get_session
from qalam.errors import AppError
from qalam.net import client_ip
from qalam.ratelimit import RateLimiter
from qalam.schemas import GuestCreated, UserOut, WorkspaceOut

router = APIRouter(prefix="/v1", tags=["guest"])


def _peer_host(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    return None


@router.post("/guest", response_model=GuestCreated, status_code=201)
def start_guest(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> GuestCreated:
    settings = request.app.state.settings
    if not settings.guest_access:
        raise AppError("guest_disabled", "Guest access is not enabled.", 404)

    ip = client_ip(
        request.headers.get("x-forwarded-for"),
        _peer_host(request),
        settings.trusted_proxy_hops,
    )
    redis = request.app.state.redis
    per_ip_limit = settings.guest_signups_per_minute
    total_limit = settings.guest_signups_per_minute_total
    ip_allowed, ip_remaining = RateLimiter(redis, per_ip_limit).hit(f"guest:{ip}")
    total_allowed, _total_remaining = RateLimiter(redis, total_limit).hit("guest:all")
    response.headers["X-RateLimit-Limit"] = str(per_ip_limit)
    response.headers["X-RateLimit-Remaining"] = str(ip_remaining)
    if not ip_allowed or not total_allowed:
        raise AppError("rate_limited", "Too many requests.", 429, headers={"Retry-After": "60"})

    user, workspace, raw = create_guest(session)
    return GuestCreated(
        api_key=raw,
        workspace=WorkspaceOut.model_validate(workspace),
        user=UserOut.model_validate(user),
    )
