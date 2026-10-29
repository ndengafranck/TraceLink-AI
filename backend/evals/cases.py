"""Fixed evaluation cases: synthetic sightings (never real people's data).

Each case is a list of (minutes_ago, lat, lon, accuracy_m, flags, source). Cases cover
the situations that matter: clean, stale, rough, impossible jump, mixed, many, Bluetooth,
empty. Locations are synthetic points in Douala and Yaounde.
"""

from datetime import datetime, timedelta, timezone

from app.models import Observation

D = (4.0511, 9.7679)   # Douala
Y = (3.8480, 11.5021)  # Yaounde


def p(mins, place=D, acc=30.0, flags=(), source="simulated", dlat=0.0):
    return (mins, place[0] + dlat, place[1], acc, list(flags), source)


CASES = {
    "single_fresh": [p(5)],
    "fresh_cluster": [p(12), p(8, dlat=0.0008), p(4, dlat=0.0015)],
    "stale_only": [p(60 * 30, flags=["stale"])],
    "low_accuracy_only": [p(10, acc=5200, flags=["low_accuracy"])],
    "impossible_jump": [p(10), p(8, place=Y, flags=["implausible_movement"])],
    "everything_mixed": [p(6), p(20, dlat=0.001), p(60 * 28, flags=["stale"]),
                         p(15, acc=4000, flags=["low_accuracy"]),
                         p(9, place=Y, flags=["implausible_movement"])],
    "many_sightings": [p(5 + 7 * i, dlat=0.0002 * i) for i in range(30)],
    "bluetooth_only": [p(3, source="ble", acc=80), p(25, source="ble", acc=70, dlat=0.001)],
    "bluetooth_and_demo": [p(4, source="ble", acc=80), p(30, dlat=0.001), p(60 * 26, flags=["stale"])],
    "empty_case": [],
}


def build(name: str, now: datetime | None = None) -> list[Observation]:
    """Unsaved Observation objects: the AI module only reads their attributes."""
    now = now or datetime.now(timezone.utc)
    out = []
    for i, (mins, lat, lon, acc, flags, source) in enumerate(CASES[name]):
        out.append(Observation(
            id=f"eval-{name}-{i:03d}", case_id="eval", source=source,
            observed_at=now - timedelta(minutes=mins), received_at=now, lat=lat, lon=lon,
            accuracy_m=acc, nonce=f"n{i}", flags=flags,
            validation_status="flagged" if flags else "accepted"))
    return out
