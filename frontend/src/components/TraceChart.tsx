import { useMemo, useState } from "react";
import type { Observation } from "../api";
import { label, project } from "../geo";

export const FLAG_TEXT: Record<string, string> = {
  stale: "Over 24 hours old",
  low_accuracy: "Error margin over 1 km",
  implausible_movement: "Needs an impossible speed to fit its neighbours",
};

/** Sighting numbers follow time order: 1 is the earliest. */
export function numbering(obs: Observation[]): Map<string, number> {
  const sorted = [...obs].sort((a, b) => +new Date(a.observed_at) - +new Date(b.observed_at));
  return new Map(sorted.map((o, i) => [o.id, i + 1]));
}

const W = 760, H = 520, PAD = 70, EDGE = 30;

interface Props {
  observations: Observation[];
  lit: Set<string>;                 // ids to emphasise (hover or AI citation)
  onHover: (id: string | null) => void;
}

interface Placed { o: Observation; x: number; y: number; ax: number; ay: number; off: boolean; away: string }

/** Move markers that sit on top of each other apart, so every number stays readable. */
function spread(items: Placed[]): void {
  const groups: Placed[][] = [];
  for (const it of items) {
    const g = groups.find((grp) => Math.hypot(grp[0].ax - it.ax, grp[0].ay - it.ay) < 22);
    g ? g.push(it) : groups.push([it]);
  }
  for (const g of groups) {
    if (g.length < 2) continue;
    const cx = g.reduce((a, m) => a + m.ax, 0) / g.length;
    const cy = g.reduce((a, m) => a + m.ay, 0) / g.length;
    const r = 13 + g.length * 4;
    g.forEach((m, i) => {
      const a = (i / g.length) * Math.PI * 2 - Math.PI / 2;
      m.x = cx + Math.cos(a) * r; m.y = cy + Math.sin(a) * r;
    });
  }
}

export function TraceChart({ observations, lit, onHover }: Props) {
  const [focus, setFocus] = useState<"passed" | "all">("passed");
  const nums = useMemo(() => numbering(observations), [observations]);
  const passed = observations.filter((o) => o.validation_status === "accepted");
  const canFocus = passed.length > 0 && passed.length < observations.length;
  const fit = canFocus && focus === "passed" ? passed : observations;
  const proj = useMemo(() => project(fit, W, H, PAD), [fit]);

  const placed = useMemo(() => {
    const items: Placed[] = observations.map((o) => {
      const [rx, ry] = proj.xy(o.lat, o.lon);
      const x = Math.min(W - EDGE, Math.max(EDGE, rx));
      const y = Math.min(H - EDGE, Math.max(EDGE, ry));
      const off = x !== rx || y !== ry;
      const away = off ? label(Math.hypot(rx - W / 2, ry - H / 2) / proj.pxPerMetre) : "";
      return { o, x, y, ax: x, ay: y, off, away };
    });
    spread(items);
    return items.sort((a, b) => +new Date(a.o.observed_at) - +new Date(b.o.observed_at));
  }, [observations, proj]);

  const dimming = lit.size > 0;
  const path = placed.map((m, i) => `${i ? "L" : "M"}${m.x} ${m.y}`).join(" ");

  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`Chart of ${observations.length} sightings`}>
        {proj.gridX.map((x) => <line key={`x${x}`} x1={x} x2={x} y1={0} y2={H} stroke="#c9d6d2" strokeWidth="1" />)}
        {proj.gridY.map((y) => <line key={`y${y}`} x1={0} x2={W} y1={y} y2={y} stroke="#c9d6d2" strokeWidth="1" />)}

        {placed.length > 1 && <path d={path} fill="none" stroke="#13222e" strokeWidth="1.5" strokeDasharray="6 5" opacity=".5" />}

        {placed.filter((m) => !m.off).map(({ o, ax, ay }) => {
          const flagged = o.validation_status === "flagged";
          return (
            <circle key={`r${o.id}`} cx={ax} cy={ay} r={Math.max(14, o.accuracy_m * proj.pxPerMetre)}
              className={dimming && !lit.has(o.id) ? "dim" : ""}
              fill={flagged ? "rgba(179,18,107,.08)" : "rgba(11,110,106,.09)"}
              stroke={flagged ? "#b3126b" : "#0b6e6a"} strokeWidth="1.2" strokeDasharray="3 3" />
          );
        })}

        {placed.map(({ o, x, y, off, away }) => {
          const flagged = o.validation_status === "flagged";
          const on = lit.has(o.id);
          const n = nums.get(o.id);
          const label = `Sighting ${n}, ${flagged ? "flagged: " + o.flags.map((f) => FLAG_TEXT[f] ?? f).join(", ") : "passed all checks"}, error ${Math.round(o.accuracy_m)} metres${off ? `, about ${away} outside this view` : ""}`;
          return (
            <g key={o.id} className={`marker ${dimming && !on ? "dim" : ""}`} tabIndex={0} role="img" aria-label={label}
              transform={`translate(${x} ${y})`}
              onMouseEnter={() => onHover(o.id)} onMouseLeave={() => onHover(null)}
              onFocus={() => onHover(o.id)} onBlur={() => onHover(null)}>
              <circle className="halo" r={on ? 22 : 19} stroke={on ? "#13222e" : undefined} strokeWidth={on ? 3 : 0} />
              {flagged
                ? <rect x="-12" y="-12" width="24" height="24" rx="4" fill="#b3126b" transform="rotate(45)" />
                : <circle r="13" fill="#0b6e6a" />}
              <text textAnchor="middle" dy="4.5" fontSize="13" fontWeight="700" fill="#fff" style={{ pointerEvents: "none" }}>{n}</text>
              {off && (
                <text y={x > W / 2 ? 30 : -22} textAnchor={x > W - 90 ? "end" : x < 90 ? "start" : "middle"}
                  fontSize="12" fontWeight="600" fill="#7a0b49" style={{ pointerEvents: "none" }}>{away} away →</text>
              )}
            </g>
          );
        })}

        <g transform={`translate(${W - 36} 44)`} aria-hidden="true">
          <path d="M0 -22 L9 10 L0 4 L-9 10 Z" fill="#13222e" />
          <text y="26" textAnchor="middle" fontSize="12" fontWeight="700" fill="#13222e">N</text>
        </g>
        <g transform={`translate(24 ${H - 26})`} aria-hidden="true">
          <rect width={proj.scaleBar.px} height="5" fill="#13222e" />
          <text y="-6" fontSize="12" fontWeight="600" fill="#13222e">{proj.scaleBar.label}</text>
        </g>
      </svg>
      {canFocus && (
        <div className="focus-toggle" role="group" aria-label="Chart zoom">
          <button className={focus === "passed" ? "on" : ""} aria-pressed={focus === "passed"} onClick={() => setFocus("passed")}>Zoom to passed sightings</button>
          <button className={focus === "all" ? "on" : ""} aria-pressed={focus === "all"} onClick={() => setFocus("all")}>Show all</button>
        </div>
      )}
    </>
  );
}
