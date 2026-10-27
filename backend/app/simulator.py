"""Simulated sightings for demos and tests.

Everything produced here is stored with source "simulated" and is shown as
such. It must never be presented as a real detection. Locations are synthetic
points in Douala and Yaounde, not any real person's device.
"""

import secrets
from datetime import datetime, timedelta

DOUALA = (4.0511, 9.7679)
YAOUNDE = (3.8480, 11.5021)


def _item(now: datetime, minutes_ago: float, lat: float, lon: float, accuracy_m: float) -> dict:
    return {
        "observed_at": now - timedelta(minutes=minutes_ago),
        "lat": lat,
        "lon": lon,
        "accuracy_m": accuracy_m,
        "nonce": f"sim-{secrets.token_hex(6)}",
    }


def scenario(name: str, now: datetime) -> list[dict]:
    if name == "fresh_cluster":
        # Three nearby sightings in the last 10 minutes: a coherent trail.
        return [
            _item(now, 10, DOUALA[0], DOUALA[1], 30),
            _item(now, 6, DOUALA[0] + 0.0008, DOUALA[1] + 0.0004, 40),
            _item(now, 2, DOUALA[0] + 0.0016, DOUALA[1] + 0.0008, 35),
        ]
    if name == "stale":
        return [_item(now, 30 * 60, DOUALA[0], DOUALA[1], 50)]
    if name == "conflicting":
        # Douala then Yaounde (about 190 km) two minutes later: cannot both be right.
        return [
            _item(now, 6, DOUALA[0], DOUALA[1], 40),
            _item(now, 4, YAOUNDE[0], YAOUNDE[1], 40),
        ]
    if name == "low_accuracy":
        return [_item(now, 5, DOUALA[0], DOUALA[1], 4000)]
    raise ValueError(f"unknown scenario: {name}")
