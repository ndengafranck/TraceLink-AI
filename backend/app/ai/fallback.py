"""Deterministic explanation used when the AI is off, down, or fails the guard.

Fixed wording, no model. The product must stay useful without the AI.
"""

from app.ai.schemas import Explanation, Finding
from app.models import Observation

FLAG_TEXT = {
    "stale": "older than 24 hours, so the phone may have moved since",
    "low_accuracy": "reported with a position error above 1 km",
    "implausible_movement": "would need an impossible speed to fit with a neighbouring sighting",
}

GUIDANCE = [
    "Do not go to a location alone to look for the phone. Share it with local police.",
    "Contact your mobile operator to block the SIM and ask about blocking the device.",
    "Change the passwords of accounts that were signed in on the phone.",
    "Open this case again if new sightings arrive; they are checked the same way.",
]


def fallback_explanation(observations: list[Observation]) -> Explanation:
    if not observations:
        return Explanation(
            headline="No sightings have been received for this case yet.",
            findings=[],
            guidance=GUIDANCE,
            uncertainty=["With no sightings there is nothing to explain or locate."],
        )
    ordered = sorted(observations, key=lambda o: o.observed_at, reverse=True)
    findings = []
    clean = [o for o in ordered if o.validation_status == "accepted"]
    if clean:
        findings.append(Finding(
            text=f"{len(clean)} sighting(s) passed every automatic check.",
            observation_ids=[o.id for o in clean[:50]],
        ))
    for flag, why in FLAG_TEXT.items():
        hit = [o for o in ordered if flag in (o.flags or [])]
        if hit:
            findings.append(Finding(
                text=f"{len(hit)} sighting(s) are flagged '{flag}': {why}.",
                observation_ids=[o.id for o in hit[:50]],
            ))
    return Explanation(
        headline=f"{len(observations)} sighting(s) stored; {len(clean)} without flags.",
        findings=findings,
        guidance=GUIDANCE,
        uncertainty=[
            "A sighting shows where a finder device was, not who has the phone.",
            "Flagged sightings need extra caution before you rely on them.",
        ],
    )
