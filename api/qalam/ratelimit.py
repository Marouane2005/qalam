import time
from typing import Any

from qalam.logging import get_logger

log = get_logger("qalam.ratelimit")


class RateLimiter:
    def __init__(self, client: Any, limit: int) -> None:
        self.client = client
        self.limit = limit

    def hit(self, key_id: str) -> tuple[bool, int]:
        if self.limit <= 0:
            return True, 0
        window = int(time.time()) // 60
        redis_key = f"qalam:rl:{key_id}:{window}"
        try:
            count = int(self.client.incr(redis_key))
            if count == 1:
                self.client.expire(redis_key, 70)
        except Exception as exc:
            log.warning("rate_limit_unavailable", error=type(exc).__name__)
            return True, self.limit
        remaining = max(0, self.limit - count)
        return count <= self.limit, remaining
