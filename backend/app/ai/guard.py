"""Checks on model output. The model is untrusted until this passes.

Rules (all deterministic, English and French):
1. Every finding cites at least one id, and every cited id is a stored sighting
   of this case.
2. No decision or accusation words (stolen/volé, thief/voleur, suspect, ...).
3. Any coordinate-looking number must match a stored sighting.
4. No clock times or dates (the model's time zone differs from the screen's), and no
   leaked field names.
5. No claim about a number of sightings larger than the number stored.
"""

import re

from app.ai.schemas import Explanation, Narrative
from app.models import Observation

FORBIDDEN = re.compile(
    r"\b(stolen|steal|stole|theft|thief|thieves|criminal|culprit|guilty|suspect\w*|accus\w*|"
    r"definitely|certainly|guaranteed?|"
    r"vol[ée]e?s?|voleu[rs]e?s?|criminel\w*|coupables?|certainement|définitivement|"
    r"assurément|garanti\w*)\b",
    re.IGNORECASE,
)
COORD = re.compile(r"-?\d{1,3}\.\d{3,}")
CLOCK = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}\b|\b\d{1,2}\s?h\s?\d{2}\b", re.IGNORECASE)
FIELD_LEAK = re.compile(r"\bsource\s+(simulated|simulée?|ble)\b", re.IGNORECASE)
COUNT_CLAIM = re.compile(r"\b(\d+)\s+(?:sightings?|observations?|signalements?|détections?)\b", re.IGNORECASE)
TOLERANCE = 0.0006  # about 60 m: allows rounding to 3 or 4 decimals


def _texts(e: Explanation) -> list[str]:
    return [e.headline, *(f.text for f in e.findings), *e.guidance, *e.uncertainty]


def _check_texts(texts: list[str], observations: list[Observation]) -> list[str]:
    problems: list[str] = []
    known = [v for o in observations for v in (o.lat, o.lon)]
    for t in texts:
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
        for n in COUNT_CLAIM.findall(t):
            if int(n) > len(observations):
                problems.append(f"you wrote {n} sightings but only {len(observations)} are stored")
    return problems


def check(e: Explanation, observations: list[Observation]) -> list[str]:
    """Return a list of problems; empty means the output is acceptable."""
    valid_ids = {o.id for o in observations}
    problems = []
    for f in e.findings:
        unknown = [i for i in f.observation_ids if i not in valid_ids]
        if unknown:
            problems.append(f"finding cites unknown observation ids: {unknown}")
    return problems + _check_texts(_texts(e), observations)


def check_narrative(n: Narrative, observations: list[Observation]) -> list[str]:
    return _check_texts([n.summary, *n.requests], observations)
