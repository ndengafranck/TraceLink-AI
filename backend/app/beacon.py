"""Rotating Bluetooth IDs.

A lost phone must be recognisable to finders without being trackable by anyone
else. So the phone never broadcasts a fixed ID. Every 15 minutes it broadcasts

    beacon_id = first 8 bytes of HMAC-SHA256(secret, "tracelink-beacon:" + window)

where window = unix_time // 900. Only the owner's phone and this server know
`secret`, so nobody else can link two broadcasts to the same phone or predict
the next one. The Android app implements exactly the same formula; the test
vector in tests/test_beacon.py pins it.
"""

import hashlib
import hmac
from datetime import datetime

WINDOW_SECONDS = 900
ID_BYTES = 8
PREFIX = b"tracelink-beacon:"


def window_of(ts: datetime) -> int:
    return int(ts.timestamp() // WINDOW_SECONDS)


def beacon_id(secret: bytes, window: int) -> str:
    mac = hmac.new(secret, PREFIX + str(window).encode(), hashlib.sha256).digest()
    return mac[:ID_BYTES].hex()


def matches(secret: bytes, seen_id: str, observed_at: datetime) -> bool:
    """True if `seen_id` is this secret's ID for the sighting's window or a neighbour.

    The neighbours absorb clock differences and a broadcast that straddles a boundary.
    """
    w = window_of(observed_at)
    ok = False
    for candidate in (w - 1, w, w + 1):  # no early exit: constant work
        ok |= hmac.compare_digest(beacon_id(secret, candidate), seen_id)
    return ok
