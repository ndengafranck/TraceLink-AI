"""Checks on model output. The model is untrusted until this passes.

Rules (all deterministic):
1. Every finding cites at least one id, and every cited id is a stored sighting
   of this case.
2. No decision or accusation words (stolen, thief, suspect, ...).
3. Any coordinate-looking number must match a stored sighting.
4. No clock times or dates (the model's time zone differs from the screen's), and no
   leaked field names.
"""

import re

from app.ai.schemas import Explanation
from app.models import Observation

FORBIDDEN = re.compile(
    r"\b(stolen|steal|stole|theft|thief|thieves|criminal|culprit|guilty|suspect\w*|accus\w*|"
    r"definitely|certainly|guaranteed?)\b",
    re.IGNORECASE,
)
COORD = re.compile(r"-?\d{1,3}\.\d{3,}")
CLOCK = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}\b")
FIELD_LEAK = re.compile(r"\bsource\s+(simulated|ble)\b", re.IGNORECASE)
TOLERANCE = 0.0006  # about 60 m: allows rounding to 3 or 4 decimals


def _texts(e: Explanation) -> list[str]:
    return [e.headline, *(f.text for f in e.findings), *e.guidance, *e.uncertainty]


def check(e: Explanation, observations: list[Observation]) -> list[str]:
    """Return a list of problems; empty means the output is acceptable."""
    problems: list[str] = []
    valid_ids = {o.id for o in observations}
    known = [v for o in observations for v in (o.lat, o.lon)]

    for f in e.findings:
        unknown = [i for i in f.observation_ids if i not in valid_ids]
        if unknown:
            problems.append(f"finding cites unknown observation ids: {unknown}")

    for t in _texts(e):
        m = FORBIDDEN.search(t)
        if m:
            problems.append(f"forbidden word '{m.group(0)}': never state or imply a decision, "
                            "certainty or accusation")
        if CLOCK.search(t):
            problems.append("do not write clock times or dates; say how long ago instead")
        if FIELD_LEAK.search(t):
            problems.append("write 'simulated demo data' in plain words, not field names")
        for c in COORD.findall(t):
            if not any(abs(float(c) - k) <= TOLERANCE for k in known):
                problems.append(f"coordinate {c} does not match any stored sighting")
    return problems
