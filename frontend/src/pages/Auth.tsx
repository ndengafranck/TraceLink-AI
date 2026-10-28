import { FormEvent, useState } from "react";
import { api, auth } from "../api";
import { Logo } from "../components/Logo";

function Art() {
  // The page's one animated moment: a trace draws itself across a chart, once.
  const pts: [number, number, number][] = [[110, 250, 30], [220, 190, 20], [330, 215, 16], [440, 130, 36], [560, 105, 18], [660, 50, 24]];
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0]} ${p[1]}`).join(" ");
  return (
    <svg className="bg" viewBox="0 0 760 520" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      {Array.from({ length: 11 }, (_, i) => <line key={`v${i}`} x1={i * 76} x2={i * 76} y1="0" y2="520" stroke="#243746" />)}
      {Array.from({ length: 8 }, (_, i) => <line key={`h${i}`} x1="0" x2="760" y1={i * 74} y2={i * 74} stroke="#243746" />)}
      <path className="draw" d={d} fill="none" stroke="#e9eeea" strokeWidth="2" strokeDasharray="1400" />
      {pts.map(([x, y, r], i) => (
        <g key={i} className="pop" style={{ animationDelay: `${0.5 + i * 0.5}s`, transformOrigin: `${x}px ${y}px` }}>
          <circle cx={x} cy={y} r={r} fill="rgba(242,194,48,.08)" stroke="#f2c230" strokeDasharray="3 3" />
          {i === 3
            ? <rect x={x - 9} y={y - 9} width="18" height="18" rx="3" fill="#b3126b" transform={`rotate(45 ${x} ${y})`} />
            : <circle cx={x} cy={y} r="8" fill="#0b6e6a" stroke="#e9eeea" strokeWidth="2" />}
        </g>
      ))}
    </svg>
  );
}

export function AuthPage({ onDone }: { onDone: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") await api.register(email, password);
      const t = await api.login(email, password);
      auth.set(t.access_token);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <div className="auth-art">
        <Art />
        <div className="brand"><Logo /> TraceLink</div>
        <div className="copy">
          <h1>Check the trail before you trust it.</h1>
          <p>TraceLink tests every reported sighting of your lost phone with fixed rules, then explains what the evidence supports. It never says who has your phone.</p>
        </div>
      </div>
      <div className="auth-form">
        <form className="box" onSubmit={submit} noValidate>
          <h2>{mode === "login" ? "Sign in" : "Create your account"}</h2>
          <p className="muted" style={{ marginBottom: 22 }}>
            {mode === "login" ? "Welcome back." : "Register your phones now, so you are ready if one goes missing."}
          </p>
          {error && <div className="alert" role="alert">{error}</div>}
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" className="input" type="email" autoComplete="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pw">Password</label>
            <input id="pw" className="input" type="password" required value={password}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              onChange={(e) => setPassword(e.target.value)} />
            {mode === "register" && <span className="hint">At least 10 characters.</span>}
          </div>
          <button className="btn" style={{ width: "100%" }} disabled={busy || !email || !password}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
          <p className="switch muted">
            {mode === "login" ? "New here? " : "Already registered? "}
            <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
