"""Evidence engine: deterministic checks on a reported sighting.

No AI here. These are plain rules, so every decision can be explained, tested,
and shown to the user. The AI module only explains what this engine decided.

Outcome of `evaluate`:
- "rejected": the sighting is not believable at all and is NOT stored
  (future time, older than 7 days, or a near-copy of one already stored).
- "flagged":  stored, but with one or more flags the user must see.
- "accepted": stored, no flags.

Flags: stale, low_accuracy, implausible_movement.

Not a flag: a sighting from before the case was opened. A phone is usually lost
before the owner reports it, so earlier sightings are normal, not suspicious.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

MAX_FUTURE = timedelta(minutes=2)         # allowed clock difference
STALE_AFTER = timedelta(hours=24)         # older than this: flag "stale"
MAX_AGE = timedelta(days=7)               # older than this: reject
LOW_ACCURACY_M = 1000.0                   # worse than this: flag "low_accuracy"
DUPLICATE_DISTANCE_M = 30.0               # within this and ...
DUPLICATE_WINDOW_S = 120.0                # ... this long: reject as duplicate
MAX_SPEED_KMH = 250.0                     # faster than this between two sightings: flag
MIN_JUMP_KM = 1.0                         # ...but only for jumps bigger than this: GPS noise
                                          # alone can move a point by 100 m or more

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Point:
    observed_at: datetime
    lat: float
    lon: float


@dataclass(frozen=True)
class Verdict:
    status: str  # "accepted" | "flagged" | "rejected"
    flags: tuple[str, ...] = ()
    reason: str | None = None  # set only when rejected


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates, in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _is_implausible(other: Point, observed_at: datetime, lat: float, lon: float) -> bool:
    """True if getting from `other` to this sighting would need an impossible speed."""
    distance = haversine_km(other.lat, other.lon, lat, lon)
    if distance < MIN_JUMP_KM:
        return False
    seconds = max(abs((observed_at - other.observed_at).total_seconds()), 1.0)
    return distance / (seconds / 3600.0) > MAX_SPEED_KMH


def evaluate(
    *,
    observed_at: datetime,
    lat: float,
    lon: float,
    accuracy_m: float,
    existing: Sequence[Point],
    now: datetime,
) -> Verdict:
    """Judge one new sighting against the sightings already stored for the case.

    All datetimes must be timezone-aware.
    """
    if observed_at > now + MAX_FUTURE:
        return Verdict("rejected", reason="future_timestamp")
    age = now - observed_at
    if age > MAX_AGE:
        return Verdict("rejected", reason="too_old")

    for p in existing:
        close_in_time = abs((observed_at - p.observed_at).total_seconds()) <= DUPLICATE_WINDOW_S
        close_in_space = haversine_km(p.lat, p.lon, lat, lon) * 1000 <= DUPLICATE_DISTANCE_M
        if close_in_time and close_in_space:
            return Verdict("rejected", reason="duplicate")

    flags: list[str] = []
    if age > STALE_AFTER:
        flags.append("stale")
    if accuracy_m > LOW_ACCURACY_M:
        flags.append("low_accuracy")

    # Compare with the sighting just before and just after this one in time.
    before = max((p for p in existing if p.observed_at <= observed_at),
                 key=lambda p: p.observed_at, default=None)
    after = min((p for p in existing if p.observed_at > observed_at),
                key=lambda p: p.observed_at, default=None)
    neighbours = [p for p in (before, after) if p is not None]
    if any(_is_implausible(p, observed_at, lat, lon) for p in neighbours):
        flags.append("implausible_movement")

    return Verdict("flagged" if flags else "accepted", flags=tuple(flags))
