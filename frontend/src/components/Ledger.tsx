import type { Observation } from "../api";
import { ago } from "../geo";
import { FLAG_TEXT, numbering } from "./TraceChart";

interface Props {
  observations: Observation[];
  lit: Set<string>;
  onHover: (id: string | null) => void;
}

export function Ledger({ observations, lit, onHover }: Props) {
  const nums = numbering(observations);
  const rows = [...observations].sort((a, b) => +new Date(b.observed_at) - +new Date(a.observed_at));
  return (
    <ul className="ledger">
      {rows.map((o) => (
        <li key={o.id} className={`ob ${o.validation_status} ${lit.has(o.id) ? "lit" : ""}`}
          onMouseEnter={() => onHover(o.id)} onMouseLeave={() => onHover(null)}>
          <div className="badge" aria-label={`Sighting ${nums.get(o.id)}`}><span>{nums.get(o.id)}</span></div>
          <div>
            <div className="row1">
              <span>{new Date(o.observed_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</span>
              <span className="muted">{ago(o.age_seconds)}</span>
            </div>
            <div className="row2 num">
              {o.lat.toFixed(4)}, {o.lon.toFixed(4)} · error {Math.round(o.accuracy_m)} m
            </div>
            <div className="flags">
              {o.source === "simulated" && <span className="chip demo">Simulated</span>}
              {o.source === "ble" && <span className="chip plain">Bluetooth report</span>}
              {o.flags.length === 0
                ? <span className="chip">Passed every check</span>
                : o.flags.map((f) => <span key={f} className="chip flag">{FLAG_TEXT[f] ?? f}</span>)}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
