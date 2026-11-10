from fakeredis import FakeRedis

from qalam.auth import GUEST_EMAIL_SUFFIX, generate_api_key, hash_key, is_guest, key_prefix
from qalam.models import User
from qalam.ratelimit import RateLimiter


def test_api_keys_are_hashed_and_prefixed() -> None:
    raw = generate_api_key()
    assert raw.startswith("qlm_")
    assert key_prefix(raw) == raw[:8]
    assert hash_key(raw) != raw
    assert len(hash_key(raw)) == 64
    assert hash_key(raw) == hash_key(raw)


def test_rate_limiter_blocks_after_the_window_is_full() -> None:
    limiter = RateLimiter(FakeRedis(decode_responses=True), limit=2)
    assert limiter.hit("key-1")[0] is True
    assert limiter.hit("key-1")[0] is True
    allowed, remaining = limiter.hit("key-1")
    assert allowed is False
    assert remaining == 0
    assert limiter.hit("key-2")[0] is True


def test_rate_limiter_fails_open_when_redis_errors() -> None:
    class Broken:
        def incr(self, _key: str) -> int:
            raise ConnectionError("redis down")

        def expire(self, _key: str, _seconds: int) -> None:
            return None

    allowed, remaining = RateLimiter(Broken(), limit=5).hit("key")
    assert allowed is True
    assert remaining == 5


def test_is_guest_helper() -> None:
    assert is_guest(User(email=f"guest-abc{GUEST_EMAIL_SUFFIX}", name="Guest")) is True
    assert is_guest(User(email="admin@example.com", name="Admin")) is False
