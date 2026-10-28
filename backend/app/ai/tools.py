"""Read-only evidence tools the model may call.

The case is fixed by the backend when the conversation starts. The model cannot
name a case id, so it can only ever read the case the owner asked about. No tool
writes anything.
"""

import json
from datetime import datetime
from typing import Any

from app.models import Observation
from app.timeutil import aware

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_case_summary",
            "description": "Counts of stored sightings for this case and how many carry each flag.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_observations",
            "description": "Stored sightings for this case, newest first, with id, time, "
            "coordinates, accuracy, validation status and flags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "only_flagged": {"type": "boolean"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_observation",
            "description": "One stored sighting of this case by id.",
            "parameters": {
                "type": "object",
                "properties": {"observation_id": {"type": "string"}},
                "required": ["observation_id"],
                "additionalProperties": False,
            },
        },
    },
]


def observation_view(o: Observation, now: datetime) -> dict[str, Any]:
    return {
        "id": o.id,
        "source": o.source,
        "observed_at": aware(o.observed_at).isoformat(),
        "age_minutes": max(0, int((now - aware(o.observed_at)).total_seconds() // 60)),
        "lat": o.lat,
        "lon": o.lon,
        "accuracy_m": o.accuracy_m,
        "validation_status": o.validation_status,
        "flags": list(o.flags or []),
    }


def summarize(observations: list[Observation]) -> dict[str, Any]:
    flag_counts: dict[str, int] = {}
    for o in observations:
        for f in o.flags or []:
            flag_counts[f] = flag_counts.get(f, 0) + 1
    latest = max((aware(o.observed_at) for o in observations), default=None)
    return {
        "total": len(observations),
        "accepted": sum(o.validation_status == "accepted" for o in observations),
        "flagged": sum(o.validation_status == "flagged" for o in observations),
        "flag_counts": flag_counts,
        "latest_observed_at": latest.isoformat() if latest else None,
        "all_simulated": all(o.source == "simulated" for o in observations),
    }


def run_tool(name: str, raw_args: str | dict | None, observations: list[Observation],
             now: datetime) -> str:
    """Execute one tool call over this case's observations; returns a JSON string."""
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args else (raw_args or {})
        if not isinstance(args, dict):
            raise ValueError
    except ValueError:
        return json.dumps({"error": "arguments must be a JSON object"})

    if name == "get_case_summary":
        return json.dumps(summarize(observations))
    if name == "list_observations":
        rows = sorted(observations, key=lambda o: aware(o.observed_at), reverse=True)
        if args.get("only_flagged"):
            rows = [o for o in rows if o.validation_status == "flagged"]
        limit = args.get("limit", 20)
        limit = limit if isinstance(limit, int) and 1 <= limit <= 50 else 20
        return json.dumps([observation_view(o, now) for o in rows[:limit]])
    if name == "get_observation":
        oid = args.get("observation_id")
        for o in observations:
            if o.id == oid:
                return json.dumps(observation_view(o, now))
        return json.dumps({"error": "no such observation in this case"})
    return json.dumps({"error": "unknown tool"})
