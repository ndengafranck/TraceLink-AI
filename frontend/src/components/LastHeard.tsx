import type { Observation } from "../api";
import { ago } from "../geo";

/** The one answer a worried owner wants first, worked out by plain code: where was it last heard? */
export function LastHeard({ observations }: { observations: Observation[] }) {
  const reliable = observations.filter((o) => o.validation_status === "accepted");
  const last = [...reliable].sort((a, b) => +new Date(b.observed_at) - +new Date(a.observed_at))[0];
  const flagged = observations.length - reliable.length;
  const simulated = observations.length > 0 && observations.every((o) => o.source === "simulated");

  if (!last) {
    return (
      <section className="last empty-last" aria-label="Last heard">
        <h2>{observations.length ? "No reliable sighting yet" : "No sightings yet"}</h2>
        <p className="muted measure">
          {observations.length
            ? `${flagged} sighting${flagged === 1 ? " is" : "s are"} flagged and not used here. Check them in the list below.`
            : "When a finder's phone hears yours, the last place it was heard appears here."}
        </p>
      </section>
    );
  }
  const la = last.lat.toFixed(5), lo = last.lon.toFixed(5);
  const url = `https://www.openstreetmap.org/?mlat=${la}&mlon=${lo}#map=17/${la}/${lo}`;
  return (
    <section className="last" aria-label="Last heard">
      <div>
        <h2>Last heard near this point {simulated && <span className="chip demo">Demo data</span>}</h2>
        <p className="last-big">{ago(last.age_seconds)}, within about {Math.round(last.accuracy_m)} m</p>
        <p className="muted num">{last.lat.toFixed(5)}, {last.lon.toFixed(5)}</p>
        <p className="measure">It shows where a finder's phone was, not who has yours. The phone may have moved since. Do not go alone: share this with the police.</p>
      </div>
      <a className="btn teal" href={url} target="_blank" rel="noopener noreferrer">Open in OpenStreetMap</a>
    </section>
  );
}
