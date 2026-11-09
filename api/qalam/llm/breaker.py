import threading
import time


class CircuitBreaker:
    """Closed means calls go through. Open means they do not, until the cooldown elapses."""

    def __init__(self, threshold: int, cooldown_s: float) -> None:
        self.threshold = max(1, threshold)
        self.cooldown_s = cooldown_s
        self._failures = 0
        self._state = "closed"
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def allow(self) -> bool:
        with self._lock:
            if self._state == "open":
                if time.monotonic() - self._opened_at >= self.cooldown_s:
                    self._state = "half_open"
                    return True
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = "closed"

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == "half_open" or self._failures >= self.threshold:
                self._state = "open"
                self._opened_at = time.monotonic()
