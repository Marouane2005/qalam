"""Small network helpers used by HTTP routes."""


def client_ip(headers_xff: str | None, peer: str | None, hops: int) -> str:
    """Resolve the client address for rate limiting.

    When ``hops`` is <= 0, ``X-Forwarded-For`` is ignored and the peer address
    is used. When ``hops`` is positive, that many trailing XFF entries are
    treated as trusted proxies and the entry at index ``-hops`` is returned.
    """
    peer_ip = (peer or "").strip() or "unknown"
    if hops <= 0:
        return peer_ip
    parts = [part.strip() for part in (headers_xff or "").split(",") if part.strip()]
    if not parts:
        return peer_ip
    if len(parts) < hops:
        return parts[0] or peer_ip
    return parts[-hops]
