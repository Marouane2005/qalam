import pytest

from qalam.net import client_ip


@pytest.mark.parametrize(
    ("xff", "peer", "hops", "expected"),
    [
        (None, "10.0.0.5", 0, "10.0.0.5"),
        ("1.2.3.4", "10.0.0.5", 0, "10.0.0.5"),
        ("spoofed, 9.9.9.9", "10.0.0.5", 0, "10.0.0.5"),
        ("spoofed, 203.0.113.10", "10.0.0.5", 1, "203.0.113.10"),
        ("spoofed, 198.51.100.7, 203.0.113.10", "10.0.0.5", 1, "203.0.113.10"),
        ("spoofed, 198.51.100.7, 203.0.113.10", "10.0.0.5", 2, "198.51.100.7"),
        ("203.0.113.10", "10.0.0.5", 1, "203.0.113.10"),
        ("203.0.113.10", "10.0.0.5", 2, "203.0.113.10"),
        ("", "10.0.0.5", 1, "10.0.0.5"),
        (None, None, 0, "unknown"),
        (None, "", 1, "unknown"),
        ("  spoofed ,  203.0.113.10  ", "10.0.0.5", 1, "203.0.113.10"),
    ],
)
def test_client_ip(xff: str | None, peer: str | None, hops: int, expected: str) -> None:
    assert client_ip(xff, peer, hops) == expected
