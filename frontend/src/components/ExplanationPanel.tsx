import type { ExplanationResponse, Observation } from "../api";
import { numbering, FLAG_TEXT } from "./TraceChart";

const REASONS: Record<string, string> = {
  no_sightings: "There are no sightings to explain yet.",
  ai_not_configured: "The AI is not set up on this server.",
  ai_unavailable: "The AI service could not be reached.",
  ai_output_rejected: "The AI's answer failed our safety checks, so it was not shown.",
  ai_too_many_steps: "The AI took too many steps, so it was stopped.",
};

interface Props {
  busy: boolean;
  result: ExplanationResponse | null;
  observations: Observation[];
  canExplain: boolean;
  onExplain: () => void;
  onLit: (ids: string[]) => void;
}

export function ExplanationPanel({ busy, result, observations, canExplain, onExplain, onLit }: Props) {
  const nums = numbering(observations);
  return (
    <section className="explain" aria-labelledby="explain-h" aria-busy={busy}>
      <div className="topline">
        <div>
          <h2 id="explain-h">What the evidence supports</h2>
          <p style={{ color: "#b9c8d0", marginTop: 6 }} className="measure">
            Counts come from fixed rules. The explanation is written by AI and every statement points to sightings you can check.
          </p>
        </div>
        <button className="btn" onClick={onExplain} disabled={busy || !canExplain}>
          {busy ? "Reading the evidence…" : result ? "Explain again" : "Explain the evidence"}
        </button>
      </div>

      {busy && !result && (
        <div aria-hidden="true">
          <div className="skeleton" style={{ width: "60%" }} /><div className="skeleton" style={{ width: "90%" }} />
          <div className="skeleton" style={{ width: "75%" }} />
        </div>
      )}

      {result && (
        <div className="explain-body reveal" key={result.explanation.headline + result.source}>
          <div className="facts">
            <div className="src">
              <span className="big">{result.facts.total}</span>
              <span>sightings stored</span>
              <div className="pair" style={{ marginTop: 8 }}>
                <div><b>{result.facts.accepted}</b>passed</div>
                <div><b>{result.facts.flagged}</b>flagged</div>
              </div>
            </div>
            {Object.keys(result.facts.flag_counts).length > 0 && (
              <ul>
                {Object.entries(result.facts.flag_counts).map(([f, n]) => (
                  <li key={f}><b>{n}</b> × {FLAG_TEXT[f] ?? f}</li>
                ))}
              </ul>
            )}
            <div className="src">
              <b>{result.source === "ai" ? `Written by AI (${result.model})` : "Standard summary, AI not used"}</b>
              {result.source === "fallback" && result.fallback_reason && (
                <span>{REASONS[result.fallback_reason] ?? result.fallback_reason}</span>
              )}
              {result.source === "ai" && <span>Checked: every cited sighting exists, no invented places, no accusations.</span>}
            </div>
          </div>

          <div className="narrative">
            <h3>{result.explanation.headline}</h3>
            {result.explanation.findings.map((f, i) => (
              <div className="finding" key={i}>
                <p>{f.text}</p>
                <div className="cites">
                  <span className="sr">Sightings cited:</span>
                  {f.observation_ids.map((id) => nums.has(id) && (
                    <button key={id} className="cite" aria-label={`Show sighting ${nums.get(id)} on the chart`}
                      onMouseEnter={() => onLit([id])} onMouseLeave={() => onLit([])}
                      onFocus={() => onLit([id])} onBlur={() => onLit([])}>{nums.get(id)}</button>
                  ))}
                  {f.observation_ids.length > 1 && (
                    <button className="cite" onMouseEnter={() => onLit(f.observation_ids)} onMouseLeave={() => onLit([])}
                      onFocus={() => onLit(f.observation_ids)} onBlur={() => onLit([])}>All</button>
                  )}
                </div>
              </div>
            ))}

            <div className="cols">
              <div>
                <h4>What to do next</h4>
                <ul>{result.explanation.guidance.map((g, i) => <li key={i}>{g}</li>)}</ul>
              </div>
              <div className="uncertain">
                <h4>What this cannot tell you</h4>
                <ul>{result.explanation.uncertainty.map((u, i) => <li key={i}>{u}</li>)}</ul>
              </div>
            </div>
            <p style={{ marginTop: 18, color: "#b9c8d0", fontSize: ".9rem" }}>{result.notice}</p>
          </div>
        </div>
      )}
    </section>
  );
}
