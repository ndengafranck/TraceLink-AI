import type { ExplanationResponse, Lang, Observation } from "../api";
import { FLAGS, PANEL, REASONS } from "./i18n";
import { numbering } from "./TraceChart";

interface Props {
  busy: boolean;
  result: ExplanationResponse | null;
  observations: Observation[];
  canExplain: boolean;
  lang: Lang;
  onLang: (l: Lang) => void;
  onExplain: () => void;
  onLit: (ids: string[]) => void;
}

export function ExplanationPanel({ busy, result, observations, canExplain, lang, onLang, onExplain, onLit }: Props) {
  const nums = numbering(observations);
  const t = PANEL[lang];
  return (
    <section className="explain" aria-labelledby="explain-h" aria-busy={busy} lang={lang}>
      <div className="topline">
        <div>
          <h2 id="explain-h">{t.title}</h2>
          <p style={{ color: "#b9c8d0", marginTop: 6 }} className="measure">{t.intro}</p>
        </div>
        <div className="panel-actions">
          <div className="seg" role="group" aria-label={t.lang}>
            <button className={lang === "en" ? "on" : ""} aria-pressed={lang === "en"} onClick={() => onLang("en")}>English</button>
            <button className={lang === "fr" ? "on" : ""} aria-pressed={lang === "fr"} onClick={() => onLang("fr")}>Français</button>
          </div>
          <button className="btn" onClick={onExplain} disabled={busy || !canExplain}>
            {busy ? t.busy : result ? t.again : t.explain}
          </button>
        </div>
      </div>

      {busy && !result && (
        <div aria-hidden="true">
          <div className="skeleton" style={{ width: "60%" }} /><div className="skeleton" style={{ width: "90%" }} />
          <div className="skeleton" style={{ width: "75%" }} />
        </div>
      )}

      {result && (
        <div className="explain-body reveal" key={result.explanation.headline + result.source + result.language}>
          <div className="facts">
            <div className="src">
              <span className="big">{result.facts.total}</span>
              <span>{t.stored}</span>
              <div className="pair" style={{ marginTop: 8 }}>
                <div><b>{result.facts.accepted}</b>{t.passed}</div>
                <div><b>{result.facts.flagged}</b>{t.flagged}</div>
              </div>
            </div>
            {Object.keys(result.facts.flag_counts).length > 0 && (
              <ul>
                {Object.entries(result.facts.flag_counts).map(([f, n]) => (
                  <li key={f}><b>{n}</b> × {FLAGS[lang][f] ?? f}</li>
                ))}
              </ul>
            )}
            <div className="src">
              <b>{result.source === "ai" ? `${t.writtenBy} (${result.model})` : t.standard}</b>
              {result.source === "fallback" && result.fallback_reason && (
                <span>{REASONS[lang][result.fallback_reason] ?? result.fallback_reason}</span>
              )}
              {result.source === "ai" && <span>{t.checked}</span>}
            </div>
          </div>

          <div className="narrative">
            <h3>{result.explanation.headline}</h3>
            {result.explanation.findings.map((f, i) => (
              <div className="finding" key={i}>
                <p>{f.text}</p>
                <div className="cites">
                  {f.observation_ids.map((id) => nums.has(id) && (
                    <button key={id} className="cite" aria-label={t.showSighting.replace("{n}", String(nums.get(id)))}
                      onMouseEnter={() => onLit([id])} onMouseLeave={() => onLit([])}
                      onFocus={() => onLit([id])} onBlur={() => onLit([])}>{nums.get(id)}</button>
                  ))}
                  {f.observation_ids.length > 1 && (
                    <button className="cite" onMouseEnter={() => onLit(f.observation_ids)} onMouseLeave={() => onLit([])}
                      onFocus={() => onLit(f.observation_ids)} onBlur={() => onLit([])}>{t.all}</button>
                  )}
                </div>
              </div>
            ))}

            <div className="cols">
              <div>
                <h4>{t.next}</h4>
                <ul>{result.explanation.guidance.map((g, i) => <li key={i}>{g}</li>)}</ul>
              </div>
              <div className="uncertain">
                <h4>{t.cannot}</h4>
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
