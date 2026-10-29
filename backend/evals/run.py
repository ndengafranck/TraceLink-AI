"""Evaluate the AI explanation on a fixed set of cases, in English and French.

    python -m evals.run            # live if MODEL_API_KEY is set, otherwise a MOCK run
    python -m evals.run --mock     # force the scripted stand-in model (tests the harness only)
    python -m evals.run --live     # force the real model (needs MODEL_API_KEY; costs a little)

Writes evals/REPORT.md and evals/results.json. A MOCK run is labelled as such at the
top of the report: it shows the harness and the guard working, NOT how good the model is.

What is measured, per run:
  - json_ok_first: the first answer was valid JSON in the required shape
  - guard_ok_first: the first answer also passed every safety check
  - final: "ai" (an AI answer was shown) or "fallback" (fixed wording was shown, and why)
  - calls and latency
  - language_ok: the text is in the requested language (simple stop-word check)
  - findings_cited: share of findings with at least one real sighting id (guaranteed by the guard)
"""

import argparse
import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from app.ai import guard
from app.ai.client import HttpModelClient
from app.ai.service import Trace, explain
from app.config import get_settings
from evals.cases import CASES, build

LANGS = ("en", "fr")
EN_WORDS = {"the", "and", "is", "are", "of", "was", "were", "this", "that", "with", "not", "from"}
FR_WORDS = {"le", "la", "les", "des", "est", "sont", "pas", "un", "une", "du", "avec", "ce", "ces", "qui"}


def language_ok(text: str, lang: str) -> bool:
    words = re.findall(r"[a-zà-ÿ']+", text.lower())
    en, fr = sum(w in EN_WORDS for w in words), sum(w in FR_WORDS for w in words)
    return fr > en if lang == "fr" else en >= fr


class MockModel:
    """Scripted stand-in. Answers well, but deliberately breaks the first answer sometimes,
    so the guard and repair path get exercised. Not a measurement of any real model."""

    name = "mock-model"
    DEFECTS = ["bad_id", "stolen", "clock", "bad_json", "too_many"]

    def __init__(self, every: int = 3) -> None:
        """Every `every`-th run starts with a deliberate mistake, cycling through all types."""
        self.every = every
        self.runs = 0
        self.defect = None

    def chat(self, *, messages, tools=None, response_format=None):
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        if not tool_msgs:
            self.runs += 1
            self.defect = (self.DEFECTS[(self.runs // self.every - 1) % len(self.DEFECTS)]
                           if self.runs % self.every == 0 else None)
            return {"content": None, "tool_calls": [{"id": "t", "type": "function",
                    "function": {"name": "list_observations", "arguments": "{}"}}]}
        fr = "French" in messages[0]["content"]
        obs = json.loads(tool_msgs[-1]["content"])
        ids = [o["id"] for o in obs] or ["none"]
        repaired = any(m["role"] == "user" and "rejected" in m["content"] for m in messages)
        text = ("Ces signalements ont passé les contrôles et sont récents."
                if fr else "These sightings passed the checks and are recent.")
        defect = None if repaired else self.defect
        if defect == "bad_json":
            return {"content": "Sure, here is the answer."}
        cited = ["not-a-real-id"] if defect == "bad_id" else ids[:3]
        if defect == "stolen":
            text = "Le téléphone a été volé." if fr else "The phone was stolen."
        if defect == "clock":
            text = "Vu à 12h08." if fr else "Seen at 12:08."
        if defect == "too_many":
            text = "999 sightings were accepted."
        return {"content": json.dumps({
            "headline": "Résumé des signalements" if fr else "Summary of the sightings",
            "findings": [{"text": text, "observation_ids": cited}],
            "guidance": ["Contactez la police." if fr else "Contact the police."],
            "uncertainty": ["Cela ne dit pas qui a le téléphone." if fr else "This does not say who has the phone."]})}


def run(client, label: str) -> dict:
    settings = get_settings()
    rows = []
    for name in CASES:
        for lang in LANGS:
            obs = build(name)
            trace = Trace()
            t0 = time.perf_counter()
            res = explain(settings, client, obs, datetime.now(timezone.utc), lang, trace)
            dt = time.perf_counter() - t0
            text = " ".join([res.explanation.headline, *(f.text for f in res.explanation.findings),
                             *res.explanation.guidance, *res.explanation.uncertainty])
            clean = (not guard.check(res.explanation, obs)) if res.source == "ai" else None
            rows.append({
                "case": name, "language": lang, "final": res.source, "reason": res.fallback_reason,
                "json_ok_first": trace.first_json_ok, "guard_ok_first": trace.first_guard_ok,
                "repaired": trace.repaired, "problems": trace.problems[:3], "calls": trace.calls,
                "latency_s": round(dt, 2), "language_ok": language_ok(text, lang),
                "ai_output_clean": clean,
                "findings": len(res.explanation.findings),
            })
    return {"label": label, "model": client.name if client else None,
            "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows}


def pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100 * n / d:.0f}% ({n}/{d})"


def summarize(result: dict) -> str:
    rows = result["rows"]
    with_model = [r for r in rows if r["json_ok_first"] is not None]  # the model gave a first answer
    unavailable = [r for r in rows if r["reason"] == "ai_unavailable"]
    ai = [r for r in rows if r["final"] == "ai"]
    lat = sorted(r["latency_s"] for r in with_model) or [0]
    fb = {}
    for r in rows:
        if r["final"] == "fallback":
            fb[r["reason"]] = fb.get(r["reason"], 0) + 1
    head = ("**MOCK RUN. A scripted stand-in model with deliberate mistakes, not a real model. "
            "It shows the harness and the safety checks working; it says nothing about model quality.**"
            if result["label"] == "mock" else f"**LIVE RUN** of `{result['model']}`.")
    out = [f"# AI evaluation report", "", head, "",
           "Percentages count only runs where the model gave a first answer.", "",
           f"Finished: {result['finished']}  ", f"Runs: {len(rows)} ({len(CASES)} cases x {len(LANGS)} languages)", "",
           "| Measure | Result |", "|---|---|",
           f"| First answer was valid JSON in the required shape | {pct(sum(bool(r['json_ok_first']) for r in with_model), len(with_model))} |",
           f"| First answer also passed every safety check | {pct(sum(bool(r['guard_ok_first']) for r in with_model), len(with_model))} |",
           f"| Needed one repair try | {pct(sum(r['repaired'] for r in with_model), len(with_model))} |",
           f"| Final answer shown was AI-written | {pct(len(ai), len(with_model))} |",
           f"| Model did not answer (timeout or error), fixed wording shown | {len(unavailable)} runs |",
           f"| Safety checks caught a bad answer (problems found) | {sum(len(r['problems']) > 0 for r in rows)} runs |",
           f"| AI answers that still fail the checks when re-run | {sum(r['ai_output_clean'] is False for r in ai)} (must be 0) |",
           f"| Text in the requested language | {pct(sum(r['language_ok'] for r in rows), len(rows))} |",
           f"| Model calls per run (mean) | {statistics.mean(r['calls'] for r in with_model):.1f} |" if with_model else "| Model calls | n/a |",
           f"| Latency, median / slowest (seconds) | {statistics.median(lat):.1f} / {lat[-1]:.1f} |",
           "", "Fallback reasons: " + (", ".join(f"{k}: {v}" for k, v in fb.items()) or "none"), "",
           "## Every run", "", "| Case | Lang | Final | 1st JSON | 1st checks | Calls | Seconds | Problems caught |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['case']} | {r['language']} | {r['final']}{' (' + r['reason'] + ')' if r['reason'] else ''} | "
                   f"{r['json_ok_first']} | {r['guard_ok_first']} | {r['calls']} | {r['latency_s']} | "
                   f"{'; '.join(r['problems'])[:80]} |")
    out += ["", "Cases: " + ", ".join(CASES), "", "Limits: the checks are rules, not a proofreader. "
            "The language check is a simple word count. Ten cases are a smoke test, not a benchmark."]
    return "\n".join(out) + "\n"


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=str(Path(__file__).parent))
    args = ap.parse_args(argv)
    settings = get_settings()
    live = args.live or (settings.model_api_key and not args.mock)
    if live and not settings.model_api_key:
        raise SystemExit("MODEL_API_KEY is empty. Put your key in backend/.env, or use --mock.")
    client = HttpModelClient(settings) if live else MockModel()
    print(("LIVE run against " + client.name) if live else "MOCK run (scripted stand-in model)")
    result = run(client, "live" if live else "mock")
    out = Path(args.out)
    (out / "results.json").write_text(json.dumps(result, indent=2))
    (out / "REPORT.md").write_text(summarize(result))
    print((out / "REPORT.md").read_text().split("## Every run")[0])
    return result


if __name__ == "__main__":
    main()
