"""Deterministic explanation used when the AI is off, down, or fails the guard.

Fixed wording (app/ai/text.py), no model. The product must stay useful without the AI.
"""

from app.ai.schemas import Explanation, Finding
from app.ai.text import FLAG_WHY, T
from app.models import Observation


def fallback_explanation(observations: list[Observation], language: str = "en") -> Explanation:
    t = T[language]
    if not observations:
        return Explanation(
            headline=t["none_headline"], findings=[], guidance=t["guidance"],
            uncertainty=[t["none_uncertainty"]],
        )
    ordered = sorted(observations, key=lambda o: o.observed_at, reverse=True)
    findings = []
    clean = [o for o in ordered if o.validation_status == "accepted"]
    if clean:
        findings.append(Finding(text=t["passed"].format(n=len(clean)),
                                observation_ids=[o.id for o in clean[:50]]))
    for flag, why in FLAG_WHY[language].items():
        hit = [o for o in ordered if flag in (o.flags or [])]
        if hit:
            findings.append(Finding(text=t["flagged"].format(n=len(hit), flag=flag, why=why),
                                    observation_ids=[o.id for o in hit[:50]]))
    uncertainty = list(t["uncertainty"])
    if all(o.source == "simulated" for o in observations):
        uncertainty.append(t["simulated_uncertainty"])
    return Explanation(
        headline=t["headline"].format(n=len(observations), c=len(clean)),
        findings=findings, guidance=t["guidance"], uncertainty=uncertainty,
    )
