"""Orchestrates one explanation: tool loop, validation, one repair try, fallback."""

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.ai import guard
from app.ai.client import ModelClient, ModelUnavailable
from app.ai.fallback import fallback_explanation
from app.ai.schemas import Explanation, ExplanationResponse, Facts
from app.ai.tools import TOOL_SPECS, run_tool, summarize
from app.config import Settings
from app.models import Observation

MAX_MODEL_CALLS = 6

SYSTEM_PROMPT = """You explain evidence for a lost-phone recovery case to the phone's owner.
The sightings were already validated by deterministic rules; you only explain them.

Use the tools to read the case. Then answer with ONE JSON object and nothing else:
{"headline": str, "findings": [{"text": str, "observation_ids": [str]}],
 "guidance": [str], "uncertainty": [str]}

Rules:
- Every finding must cite the ids of the sightings it is about. Only cite ids returned by tools.
- Use only facts from tool results. Never invent places, times or movements.
- A sighting shows where a finder device was, not who has the phone.
- Never say or imply the phone is stolen, never blame or suspect anyone, never state certainty.
- Explain flags in plain language: stale (over 24 h old), low_accuracy (error over 1 km),
  implausible_movement (needs an impossible speed to fit a neighbouring sighting).
- Never write clock times or dates. Your times would be in a different time zone from the
  list the person is looking at. Say how long ago instead, for example "about 2 hours ago",
  using age_minutes.
- If sightings have source "simulated", say once, in the "uncertainty" list only, that they are
  simulated demo data. Do not repeat it in every finding. Never write field names such as "source".
- Guidance: safe steps only (police, mobile operator, passwords). Never advise going to a
  location alone or confronting anyone.
- "uncertainty" must list what cannot be known from this evidence.
- Plain, short sentences."""

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {"name": "explanation", "strict": True,
                    "schema": Explanation.model_json_schema()},
}


def _notice(facts: dict) -> str:
    base = "Sightings are reports to check, not proof of where the phone is or who holds it."
    if facts["total"] and facts["all_simulated"]:
        return "These sightings are SIMULATED demo data, not real detections. " + base
    return base


def _parse(content: str | None) -> Explanation:
    text = (content or "").strip()
    if text.startswith("```"):  # tolerate a fenced block
        text = text.strip("`").removeprefix("json").strip()
    return Explanation.model_validate(json.loads(text))


def explain(settings: Settings, client: ModelClient | None,
            observations: list[Observation], now: datetime) -> ExplanationResponse:
    facts = summarize(observations)

    def fallback(reason: str) -> ExplanationResponse:
        return ExplanationResponse(
            source="fallback", model=None, fallback_reason=reason,
            explanation=fallback_explanation(observations),
            facts=Facts(**facts), notice=_notice(facts),
        )

    if not observations:
        return fallback("no_sightings")
    if client is None:
        return fallback("ai_not_configured")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Explain the evidence for my case."},
    ]
    rf = RESPONSE_FORMAT if settings.model_structured_output else None
    repaired = False
    try:
        for _ in range(MAX_MODEL_CALLS):
            msg = client.chat(messages=messages, tools=TOOL_SPECS, response_format=rf)
            calls = msg.get("tool_calls") or []
            if calls:
                messages.append({"role": "assistant", "content": msg.get("content"),
                                 "tool_calls": calls})
                for c in calls:
                    fn = c.get("function", {})
                    messages.append({
                        "role": "tool", "tool_call_id": c.get("id", ""),
                        "content": run_tool(fn.get("name", ""), fn.get("arguments"),
                                            observations, now),
                    })
                continue
            try:
                exp = _parse(msg.get("content"))
                problems = guard.check(exp, observations)
            except (ValueError, ValidationError):
                exp, problems = None, ["output was not valid JSON in the required shape"]
            if not problems:
                return ExplanationResponse(
                    source="ai", model=client.name, fallback_reason=None, explanation=exp,
                    facts=Facts(**facts), notice=_notice(facts),
                )
            if repaired:
                return fallback("ai_output_rejected")
            repaired = True
            messages.append({"role": "assistant", "content": msg.get("content") or ""})
            messages.append({"role": "user", "content":
                             "Your answer was rejected: " + "; ".join(problems[:5])
                             + ". Return a corrected JSON object only."})
        return fallback("ai_too_many_steps")
    except ModelUnavailable:
        return fallback("ai_unavailable")
