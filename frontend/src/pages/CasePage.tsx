import { useCallback, useEffect, useRef, useState } from "react";
import { api, type CaseT, type Device, type ExplanationResponse, type Observation, type Scenario } from "../api";
import { ExplanationPanel } from "../components/ExplanationPanel";
import { Ledger } from "../components/Ledger";
import { Stepper } from "../components/Stepper";
import { TraceChart } from "../components/TraceChart";

const SCENARIOS: { key: Scenario; title: string; text: string }[] = [
  { key: "fresh_cluster", title: "Fresh cluster", text: "Recent sightings close together" },
  { key: "stale", title: "Stale", text: "Sightings over a day old" },
  { key: "conflicting", title: "Conflicting", text: "A jump no one could travel" },
  { key: "low_accuracy", title: "Low accuracy", text: "Position known only roughly" },
];

export function CasePage({ caseId, onBack, onError, onToast }: {
  caseId: string; onBack: () => void; onError: (m: string) => void; onToast: (m: string) => void;
}) {
  const [c, setCase] = useState<CaseT | null>(null);
  const [device, setDevice] = useState<Device | null>(null);
  const [obs, setObs] = useState<Observation[]>([]);
  const [hover, setHover] = useState<string | null>(null);
  const [cited, setCited] = useState<string[]>([]);
  const [menu, setMenu] = useState(false);
  const [busy, setBusy] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [result, setResult] = useState<ExplanationResponse | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const cs = await api.case(caseId);
      setCase(cs);
      const [d, o] = await Promise.all([api.device(cs.device_id), api.observations(caseId)]);
      setDevice(d); setObs(o);
    } catch (e) { onError((e as Error).message); }
  }, [caseId, onError]);
  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => { if (!menuRef.current?.contains(e.target as Node)) setMenu(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(false); };
    document.addEventListener("mousedown", close); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [menu]);

  const lit = new Set<string>(hover ? [hover] : cited);
  const accepting = c?.state === "open" || c?.state === "evidence_received";

  async function simulate(s: Scenario) {
    setMenu(false); setBusy(true);
    try {
      const r = await api.simulate(caseId, s);
      const stored = r.results.filter((x) => x.status !== "rejected").length;
      const rejected = r.results.length - stored;
      onToast(`${stored} sighting${stored === 1 ? "" : "s"} stored${rejected ? `, ${rejected} rejected by the rules` : ""}`);
      setResult(null); await load();
    } catch (e) { onError((e as Error).message); } finally { setBusy(false); }
  }
  async function explain() {
    setExplaining(true);
    try { setResult(await api.explain(caseId)); } catch (e) { onError((e as Error).message); } finally { setExplaining(false); }
  }
  async function move(kind: "recovered" | "close") {
    try { setCase(await (kind === "recovered" ? api.recovered(caseId) : api.close(caseId))); onToast(kind === "recovered" ? "Marked as recovered" : "Case closed"); }
    catch (e) { onError((e as Error).message); }
  }

  if (!c) return <div className="page"><p className="muted">Loading case…</p></div>;
  const simulated = obs.some((o) => o.source === "simulated");

  return (
    <div className="page">
      <a href="#/" className="crumb" onClick={(e) => { e.preventDefault(); onBack(); }}>‹ Your phones</a>
      <div className="page-head">
        <div style={{ display: "grid", gap: 14 }}>
          <h1>{device?.nickname ?? "Case"}</h1>
          <Stepper state={c.state} />
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {accepting && <button className="btn teal" onClick={() => move("recovered")}>Mark as recovered</button>}
          {c.state === "recovered" && <button className="btn" onClick={() => move("close")}>Close case</button>}
        </div>
      </div>

      {simulated && (
        <div className="demo-banner" role="note">
          <span>Demo data</span> {obs.every((o) => o.source === "simulated") ? "These sightings are simulated. They are not real detections of a real phone." : "Sightings tagged Simulated are demo data, not real detections."}
        </div>
      )}

      <div className="case-grid">
        <div className="chart-wrap">
          <div className="chart-title">
            <h2>Sightings chart</h2>
            {accepting && (
              <div className="sim-menu" ref={menuRef}>
                <button className="btn small ghost" onClick={() => setMenu((m) => !m)} aria-expanded={menu} aria-haspopup="menu" disabled={busy}>
                  {busy ? "Adding…" : "Add demo sightings"}
                </button>
                {menu && (
                  <div className="menu" role="menu">
                    {SCENARIOS.map((s) => (
                      <button key={s.key} role="menuitem" onClick={() => simulate(s.key)}><b>{s.title}</b><span>{s.text}</span></button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          {obs.length === 0
            ? <div className="empty" style={{ background: "#f2f5ef" }}>
                <h3>No sightings yet</h3>
                <p className="muted measure">Real sightings need a finder device, which is not built yet. Use “Add demo sightings” to see how the checks and the explanation work.</p>
              </div>
            : <TraceChart observations={obs} lit={lit} onHover={setHover} />}
          <div className="legend">
            <span><i className="c" />Passed checks</span>
            <span><i className="d" />Flagged</span>
            <span><i className="r" />Error margin</span>
            <span>Numbers run oldest to newest</span>
          </div>
        </div>

        <div>
          <div className="section-title"><h2>Sightings</h2><span className="muted num">{obs.length} stored</span></div>
          {obs.length === 0 ? <p className="muted">Nothing to list.</p> : <Ledger observations={obs} lit={lit} onHover={setHover} />}
        </div>
      </div>

      <ExplanationPanel busy={explaining} result={result} observations={obs} canExplain={obs.length > 0}
        onExplain={explain} onLit={setCited} />
    </div>
  );
}
