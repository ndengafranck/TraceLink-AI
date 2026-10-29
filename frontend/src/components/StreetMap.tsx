import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Observation } from "../api";
import { FLAG_TEXT, numbering } from "./TraceChart";

interface Props {
  observations: Observation[];
  lit: Set<string>;
  onHover: (id: string | null) => void;
}

/** Sightings on an OpenStreetMap street map. Same markers, rings and numbers as the chart. */
export function StreetMap({ observations, lit, onHover }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const group = useRef<L.LayerGroup | null>(null);
  const markers = useRef<Map<string, L.Marker>>(new Map());
  const hoverRef = useRef(onHover);
  hoverRef.current = onHover;
  const [focus, setFocus] = useState<"passed" | "all">("passed");

  const nums = useMemo(() => numbering(observations), [observations]);
  const passed = useMemo(() => observations.filter((o) => o.validation_status === "accepted"), [observations]);
  const canFocus = passed.length > 0 && passed.length < observations.length;

  useEffect(() => {
    const m = L.map(el.current!, { zoomControl: true }).setView([4.05, 9.77], 12);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    }).addTo(m);
    map.current = m;
    group.current = L.layerGroup().addTo(m);
    const mk = markers.current;
    return () => { m.remove(); map.current = null; mk.clear(); };
  }, []);

  useEffect(() => {
    const m = map.current, g = group.current;
    if (!m || !g) return;
    g.clearLayers();
    markers.current.clear();
    const ordered = [...observations].sort((a, b) => +new Date(a.observed_at) - +new Date(b.observed_at));
    if (ordered.length > 1) {
      L.polyline(ordered.map((o) => [o.lat, o.lon] as [number, number]),
        { color: "#13222e", weight: 1.5, dashArray: "6 5", opacity: 0.5 }).addTo(g);
    }
    for (const o of ordered) {
      const flagged = o.validation_status === "flagged";
      const color = flagged ? "#b3126b" : "#0b6e6a";
      L.circle([o.lat, o.lon], { radius: Math.max(o.accuracy_m, 8), color, weight: 1.2, dashArray: "3 3",
        fillColor: color, fillOpacity: 0.09, interactive: false }).addTo(g);
      const n = nums.get(o.id);
      const label = `Sighting ${n}, ${flagged ? "flagged: " + o.flags.map((f) => FLAG_TEXT[f] ?? f).join(", ") : "passed all checks"}, error ${Math.round(o.accuracy_m)} metres`;
      const mk = L.marker([o.lat, o.lon], {
        icon: L.divIcon({ className: "lm-wrap", iconSize: [30, 30], iconAnchor: [15, 15],
          html: `<div class="lm ${flagged ? "flag" : "ok"}"><span>${n}</span></div>` }),
        title: label, alt: label, keyboard: true,
      }).addTo(g);
      mk.on("mouseover", () => hoverRef.current(o.id));
      mk.on("mouseout", () => hoverRef.current(null));
      const dom = mk.getElement();
      dom?.addEventListener("focus", () => hoverRef.current(o.id));
      dom?.addEventListener("blur", () => hoverRef.current(null));
      markers.current.set(o.id, mk);
    }
    const fit = canFocus && focus === "passed" ? passed : observations;
    if (fit.length === 1) m.setView([fit[0].lat, fit[0].lon], 16);
    else if (fit.length > 1) {
      m.fitBounds(L.latLngBounds(fit.map((o) => [o.lat, o.lon] as [number, number])).pad(0.35), { maxZoom: 17 });
    }
  }, [observations, nums, focus, canFocus, passed]);

  useEffect(() => {
    markers.current.forEach((mk, id) => {
      const dom = mk.getElement();
      dom?.classList.toggle("lit", lit.has(id));
      dom?.classList.toggle("dim", lit.size > 0 && !lit.has(id));
    });
  }, [lit, observations, focus]);

  return (
    <>
      <div ref={el} className="street" role="group" aria-label={`Street map of ${observations.length} sightings`} />
      {canFocus && (
        <div className="focus-toggle" role="group" aria-label="Map zoom">
          <button className={focus === "passed" ? "on" : ""} aria-pressed={focus === "passed"} onClick={() => setFocus("passed")}>Zoom to passed sightings</button>
          <button className={focus === "all" ? "on" : ""} aria-pressed={focus === "all"} onClick={() => setFocus("all")}>Show all</button>
        </div>
      )}
      <p className="muted" style={{ fontSize: ".82rem", margin: "10px 4px 0" }}>
        Map tiles come from OpenStreetMap, which sees the area you are viewing, not your account or case.
      </p>
    </>
  );
}
