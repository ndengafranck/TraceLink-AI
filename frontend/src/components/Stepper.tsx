import type { CaseState } from "../api";

const STEPS: { key: CaseState; label: string }[] = [
  { key: "open", label: "Reported" },
  { key: "evidence_received", label: "Sightings received" },
  { key: "recovered", label: "Recovered" },
  { key: "closed", label: "Closed" },
];

export function Stepper({ state }: { state: CaseState }) {
  const at = STEPS.findIndex((s) => s.key === state);
  return (
    <ol className="stepper" aria-label="Case progress">
      {STEPS.map((s, i) => (
        <li key={s.key} className={i < at ? "done" : i === at ? "now" : ""} aria-current={i === at ? "step" : undefined}>
          <span className="dot" aria-hidden="true" />
          {s.label}
        </li>
      ))}
    </ol>
  );
}
