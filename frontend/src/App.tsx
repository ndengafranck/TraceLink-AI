import { useCallback, useEffect, useState } from "react";
import { api, auth, type User } from "./api";
import { Logo } from "./components/Logo";
import { Toast } from "./components/Toast";
import { AuthPage } from "./pages/Auth";
import { CasePage } from "./pages/CasePage";
import { DevicesPage } from "./pages/Devices";

function parse(hash: string): { caseId: string | null } {
  const m = /^#\/cases\/([\w-]+)$/.exec(hash);
  return { caseId: m ? m[1] : null };
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(!auth.hasToken);
  const [route, setRoute] = useState(parse(location.hash));
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    auth.onUnauthorized(() => { setUser(null); setError("Your session ended. Sign in again."); });
    if (auth.hasToken) api.me().then(setUser).catch(() => auth.set(null)).finally(() => setReady(true));
    const h = () => setRoute(parse(location.hash));
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);

  const fail = useCallback((m: string) => setToast(m), []);
  const ok = useCallback((m: string) => setToast(m), []);

  if (!ready) return null;
  if (!user) {
    return (
      <>
        <AuthPage onDone={() => api.me().then((u) => { setUser(u); setError(null); location.hash = "#/"; })} />
        {error && <Toast text={error} onDone={() => setError(null)} />}
      </>
    );
  }

  const go = (hash: string) => { location.hash = hash; };
  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/"><Logo /> TraceLink</a>
        <div className="who">
          <span>{user.email}</span>
          <button className="btn ghost small" onClick={() => { auth.set(null); setUser(null); location.hash = "#/"; }}>Sign out</button>
        </div>
      </header>
      <main>
        {route.caseId
          ? <CasePage key={route.caseId} caseId={route.caseId} onBack={() => go("#/")} onError={fail} onToast={ok} />
          : <DevicesPage onOpenCase={(id) => go(`#/cases/${id}`)} onError={fail} onToast={ok} />}
      </main>
      {toast && <Toast text={toast} onDone={() => setToast(null)} />}
    </>
  );
}
