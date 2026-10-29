"""Builds the report draft text. Every fact is added here, by code.

The model contributes only the narrative (summary and requests). The phone
details, the sighting list and the notes come from the database, so a draft
can never contain a fact the system does not hold. The full IMEI is never
included: the owner writes it in by hand.
"""

from datetime import datetime

from app.ai.schemas import Narrative
from app.ai.text import R
from app.models import Case, Device, Observation
from app.timeutil import aware

MAX_LISTED = 15


def _utc(dt: datetime) -> str:
    return aware(dt).strftime("%Y-%m-%d %H:%M UTC")


def fallback_narrative(observations: list[Observation], language: str, audience: str) -> Narrative:
    r = R[language]
    passed = sum(o.validation_status == "accepted" for o in observations)
    summary = r["fallback_summary"].format(n=len(observations), p=passed, f=len(observations) - passed)
    return Narrative(summary=summary, requests=r["fallback_ask"][audience])


def build_body(
    *, language: str, audience: str, device: Device, case: Case, ownership_channel: str | None,
    observations: list[Observation], narrative: Narrative, prepared_at: datetime,
) -> tuple[str, str]:
    """Returns (title, full text)."""
    r = R[language]
    c = " : " if language == "fr" else ": "  # French puts a space before the colon
    own = {"demo": r["own_demo"], "companion_app": r["own_phone"]}.get(ownership_channel or "", r["own_none"])
    ordered = sorted(observations, key=lambda o: aware(o.observed_at))
    passed = sum(o.validation_status == "accepted" for o in observations)

    lines = [r["title"][audience], _utc(prepared_at), "", r["phone"],
             f"{r['model']}{c}{device.model}", f"{r['nickname']}{c}{device.nickname}",
             f"{r['imei']}{c}" + r["imei_value"].format(last4=device.imei_last4),
             f"{r['ownership']}{c}{own}", f"{r['opened']}{c}{_utc(case.opened_at)}", "",
             r["summary"], narrative.summary, "",
             r["sightings"].format(n=len(observations), p=passed, f=len(observations) - passed)]
    if not ordered:
        lines.append(r["no_sightings"])
    for i, o in enumerate(ordered[:MAX_LISTED], 1):
        flags = ", ".join(r["flags"].get(f, f) for f in (o.flags or [])) or r["no_flags"]
        lines.append(f"{i}. {_utc(o.observed_at)} | {o.lat:.4f}, {o.lon:.4f} | "
                     f"{r['error'].format(m=round(o.accuracy_m))} | {flags}")
    if len(ordered) > MAX_LISTED:
        lines.append(r["more"].format(n=len(ordered) - MAX_LISTED))
    lines += ["", r["ask"], *[f"- {x}" for x in narrative.requests], "", r["note"]]
    if observations and all(o.source == "simulated" for o in observations):
        lines.append(r["sim_note"])
    lines.append(r["footer"])
    return r["title"][audience], "\n".join(lines)
