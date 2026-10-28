import type { Observation } from "./api";

const M_PER_DEG_LAT = 110574;
const M_PER_DEG_LON = 111320;

export interface Projection {
  xy: (lat: number, lon: number) => [number, number];
  pxPerMetre: number;
  gridX: number[];
  gridY: number[];
  scaleBar: { px: number; label: string };
}

function niceStep(rawMetres: number): number {
  const pow = 10 ** Math.floor(Math.log10(rawMetres));
  const n = rawMetres / pow;
  return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * pow;
}

export function label(metres: number): string {
  return metres >= 1000 ? `${+(metres / 1000).toFixed(1)} km` : `${Math.round(metres)} m`;
}

/** Fit sightings into a w x h box using a local flat projection (fine at city scale). */
export function project(obs: Observation[], w: number, h: number, pad: number): Projection {
  const lat0 = obs.length ? obs.reduce((s, o) => s + o.lat, 0) / obs.length : 0;
  const lon0 = obs.length ? obs.reduce((s, o) => s + o.lon, 0) / obs.length : 0;
  const kx = Math.cos((lat0 * Math.PI) / 180) * M_PER_DEG_LON;
  const toM = (lat: number, lon: number): [number, number] => [(lon - lon0) * kx, (lat - lat0) * M_PER_DEG_LAT];

  const pts = obs.map((o) => toM(o.lat, o.lon));
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const spanX = Math.max(600, (Math.max(0, ...xs) - Math.min(0, ...xs)) * 1.0);
  const spanY = Math.max(600, (Math.max(0, ...ys) - Math.min(0, ...ys)) * 1.0);
  const cx = obs.length ? (Math.max(...xs) + Math.min(...xs)) / 2 : 0;
  const cy = obs.length ? (Math.max(...ys) + Math.min(...ys)) / 2 : 0;
  const s = Math.min((w - 2 * pad) / spanX, (h - 2 * pad) / spanY);

  const xy = (lat: number, lon: number): [number, number] => {
    const [mx, my] = toM(lat, lon);
    return [w / 2 + (mx - cx) * s, h / 2 - (my - cy) * s];
  };

  const step = niceStep(80 / s); // grid line about every 80 px
  const lines = (size: number, centre: number) => {
    const half = size / s / 2;
    const out: number[] = [];
    for (let m = Math.ceil((centre - half) / step) * step; m <= centre + half; m += step) out.push(m);
    return out;
  };
  return {
    xy,
    pxPerMetre: s,
    gridX: lines(w, cx).map((m) => w / 2 + (m - cx) * s),
    gridY: lines(h, cy).map((m) => h / 2 - (m - cy) * s),
    scaleBar: { px: step * s, label: label(step) },
  };
}

export function ago(seconds: number): string {
  if (seconds < 90) return "just now";
  const m = Math.round(seconds / 60);
  if (m < 90) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 36) return `${h} h ago`;
  return `${Math.round(h / 24)} days ago`;
}

export function isValidImei(v: string): boolean {
  if (!/^\d{15}$/.test(v)) return false;
  let sum = 0;
  for (let i = 0; i < 15; i++) {
    let d = Number(v[14 - i]);
    if (i % 2 === 1) { d *= 2; if (d > 9) d -= 9; }
    sum += d;
  }
  return sum % 10 === 0;
}
