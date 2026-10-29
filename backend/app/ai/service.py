"""Runs the model: tool loop, validation, one repair try, then a fixed fallback.

Two jobs use the same loop: explaining the evidence, and writing the narrative
of a report draft. Both have the same safety net (schema, guard, fallback).
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.ai import guard
from app.ai.client import ModelClient, ModelUnavailable
from app.ai.fallback import fallback_explanation
from app.ai.schemas import Explanation, ExplanationResponse, Facts, Narrative
from app.ai.text import LANGUAGE_NAME, T
from app.ai.tools import TOOL_SPECS, run_tool, summarize
from app.config import Settings
from app.models import Observation

MAX_MODEL_CALLS = 6

COMMON_RULES = """Rules:
- Use only facts from tool results. Never invent places, times or movements.
- A sighting shows where a finder device was, not who has the phone.
- Never say or imply the phone is stolen, never blame or suspect anyone, never state certainty.
- Never write clock times or dates. Your times would be in a different time zone from the
  list the person is looking at. Say how long ago instead, for example "about 2 hours ago",
  using age_minutes.
- Never write the number of sightings as more than the case has. Never write field names such as "source".
- Plain, short sentences.
- Write every text field in {language}. Keep the JSON keys exactly as shown, in English."""

EXPLAIN_PROMPT = """You explain evidence for a lost-phone recovery case to the phone's owner.
The sightings were already validated by deterministic rules; you only explain them.

A counted summary of the case is already given in the user message, so do not call
get_case_summary. Call list_observations once to read the sightings. Then answer with ONE JSON
object and nothing else:
{{"headline": str, "findings": [{{"text": str, "observation_ids": [str]}}],
 "guidance": [str], "uncertainty": [str]}}

Extra rules:
- Every finding must cite the ids of the sightings it is about. Only cite ids returned by tools.
- Explain flags in plain language: stale (over 24 h old), low_accuracy (error over 1 km),
  implausible_movement (needs an impossible speed to fit a neighbouring sighting).
- If sightings have source "simulated", say once, in the "uncertainty" list only, that they are
  simulated demo data. Do not repeat it in every finding.
- Guidance: safe steps only (police, mobile operator, passwords). Never advise going to a
  location alone or confronting anyone.
- "uncertainty" must list what cannot be known from this evidence.
""" + COMMON_RULES

NARRATIVE_PROMPT = """You help the owner of a lost phone write a short, factual message to {audience}.
Another program will add the phone details and the list of sightings, so do NOT list them.
You write only two things, from the tool results.

A counted summary of the case is already given in the user message, so do not call
get_case_summary. Call list_observations once to read the sightings. Then answer with ONE JSON
object and nothing else:
{{"summary": str, "requests": [str]}}

Extra rules:
- "summary": 2 to 4 sentences, first person ("my phone"), saying what the evidence shows and how
  reliable it is (how many sightings, how many are flagged and why, how recent).
- "requests": 1 to 4 short, polite things the owner asks of {audience}.
  Police: record the report, advise on next steps. Mobile operator: block the SIM, block the device
  by IMEI, confirm in writing. Never ask them to track or confront anyone.
- Do not write the IMEI or any number that is not in the tool results.
""" + COMMON_RULES

AUDIENCE_TEXT = {"police": "the police", "operator": "the owner's mobile operator"}


@dataclass
class Trace:
    """What happened inside one run. Used by the evaluation, not by the API."""

    calls: int = 0
    first_json_ok: bool | None = None
    first_guard_ok: bool | None = None
    repaired: bool = False
    problems: list[str] = field(default_factory=list)


def response_format(model_cls) -> dict:
    return {"type": "json_schema", "json_schema": {
        "name": model_cls.__name__.lower(), "strict": True, "schema": model_cls.model_json_schema()}}


def _parse(model_cls, content: str | None):
    text = (content or "").strip()
    if text.startswith("```"):  # tolerate a fenced block
        text = text.strip("`").removeprefix("json").strip()
    return model_cls.model_validate(json.loads(text))


def _converse(
    settings: Settings,
    client: ModelClient,
    observations: list[Observation],
    now: datetime,
    system: str,
    user: str,
    model_cls,
    check: Callable[[Any], list[str]],
    trace: Trace,
) -> tuple[Any | None, str | None]:
    """Returns (validated output, None) or (None, reason for falling back)."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system}, {"role": "user", "content": user}]
    rf = response_format(model_cls) if settings.model_structured_output else None
    try:
        for _ in range(MAX_MODEL_CALLS):
            msg = client.chat(messages=messages, tools=TOOL_SPECS, response_format=rf)
            trace.calls += 1
            calls = msg.get("tool_calls") or []
            if calls:
                messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
                for c in calls:
                    fn = c.get("function", {})
                    messages.append({"role": "tool", "tool_call_id": c.get("id", ""),
                                     "content": run_tool(fn.get("name", ""), fn.get("arguments"),
                                                         observations, now)})
                continue
            try:
                out = _parse(model_cls, msg.get("content"))
                problems = check(out)
                json_ok = True
            except (ValueError, ValidationError):
                out, problems, json_ok = None, ["output was not valid JSON in the required shape"], False
            if trace.first_json_ok is None:
                trace.first_json_ok, trace.first_guard_ok = json_ok, not problems
            if not problems:
                return out, None
            trace.problems.extend(problems)
            if trace.repaired:
                return None, "ai_output_rejected"
            trace.repaired = True
            messages.append({"role": "assistant", "content": msg.get("content") or ""})
            messages.append({"role": "user", "content": "Your answer was rejected: "
                             + "; ".join(problems[:5]) + ". Return a corrected JSON object only."})
        return None, "ai_too_many_steps"
    except ModelUnavailable:
        return None, "ai_unavailable"


def notice(facts: dict, language: str) -> str:
    t = T[language]
    return (t["notice_sim"] if facts["total"] and facts["all_simulated"] else "") + t["notice_base"]


def explain(settings: Settings, client: ModelClient | None, observations: list[Observation],
            now: datetime, language: str = "en", trace: Trace | None = None) -> ExplanationResponse:
    trace = trace or Trace()
    facts = summarize(observations)

    def fallback(reason: str) -> ExplanationResponse:
        return ExplanationResponse(
            source="fallback", language=language, model=None, fallback_reason=reason,
            explanation=fallback_explanation(observations, language),
            facts=Facts(**facts), notice=notice(facts, language))

    if not observations:
        return fallback("no_sightings")
    if client is None:
        return fallback("ai_not_configured")
    exp, reason = _converse(
        settings, client, observations, now,
        EXPLAIN_PROMPT.format(language=LANGUAGE_NAME[language]),
        f"Case summary (counted by the system): {json.dumps(facts)}\nExplain the evidence for my case.",
        Explanation,
        lambda e: guard.check(e, observations), trace)
    if exp is None:
        return fallback(reason or "ai_output_rejected")
    return ExplanationResponse(source="ai", language=language, model=client.name,
                               fallback_reason=None, explanation=exp,
                               facts=Facts(**facts), notice=notice(facts, language))


def write_narrative(settings: Settings, client: ModelClient | None, observations: list[Observation],
                    now: datetime, language: str, audience: str,
                    trace: Trace | None = None) -> tuple[Narrative | None, str | None]:
    """The model's part of a report draft. (None, reason) means: use the fixed wording."""
    if not observations:
        return None, "no_sightings"
    if client is None:
        return None, "ai_not_configured"
    return _converse(
        settings, client, observations, now,
        NARRATIVE_PROMPT.format(language=LANGUAGE_NAME[language], audience=AUDIENCE_TEXT[audience]),
        f"Case summary (counted by the system): {json.dumps(summarize(observations))}\n"
        "Write the summary and requests for my report.", Narrative,
        lambda n: guard.check_narrative(n, observations), trace or Trace())
