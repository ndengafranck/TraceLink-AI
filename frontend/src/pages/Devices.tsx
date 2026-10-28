import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, type CaseT, type Challenge, type Device } from "../api";
import { isValidImei } from "../geo";

const ACTIVE = ["open", "evidence_received"];

function VerifyBox({ device, onDone, onError }: { device: Device; onDone: () => void; onError: (m: string) => void }) {
  const [mode, setMode] = useState<"phone" | "demo" | null>(null);
  const [ch, setCh] = useState<Challenge | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  async function demo() {
    setBusy(true);
    try { setCh(await api.challenge(device.id)); setMode("demo"); }
    catch (e) { onError((e as Error).message); } finally { setBusy(false); }
  }
  async function confirm(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try { await api.verify(device.id, code); onDone(); } catch (e2) { onError((e2 as Error).message); } finally { setBusy(false); }
  }

  if (!mode) {
    return (
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button className="btn teal small" onClick={() => setMode("phone")}>Prove this phone is yours</button>
        <button className="btn ghost small" onClick={demo} disabled={busy}>Use a demo code</button>
      </div>
    );
  }
  return (
    <form className="verify" onSubmit={confirm}>
      {mode === "phone" && (
        <p>On the phone, open the TraceLink app, choose this phone, and tap <b>Show my code</b>. Then type the 6 digits here.</p>
      )}
      {mode === "demo" && ch?.code && (
        <div>
          <span className="chip demo">Demo</span>
          <p className="muted" style={{ margin: "6px 0 2px" }}>Normally this code appears on the phone. In demo mode the server shows it here.</p>
          <div className="code-box" aria-label={`Demo code ${ch.code.split("").join(" ")}`}>{ch.code}</div>
        </div>
      )}
      <div className="field" style={{ margin: 0 }}>
        <label htmlFor={`c${device.id}`}>6-digit code</label>
        <input id={`c${device.id}`} className="input num" inputMode="numeric" maxLength={6} autoComplete="one-time-code"
          value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn teal small" disabled={busy || code.length !== 6}>Confirm code</button>
        <button type="button" className="btn ghost small" onClick={() => { setMode(null); setCh(null); setCode(""); }}>Back</button>
      </div>
    </form>
  );
}

export function DevicesPage({ onOpenCase, onError, onToast }: {
  onOpenCase: (id: string) => void; onError: (m: string) => void; onToast: (m: string) => void;
}) {
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [cases, setCases] = useState<CaseT[]>([]);
  const [nickname, setNickname] = useState("");
  const [model, setModel] = useState("");
  const [imei, setImei] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [d, c] = await Promise.all([api.devices(), api.cases()]);
      setDevices(d); setCases(c);
    } catch (e) { onError((e as Error).message); setDevices([]); }
  }, [onError]);
  useEffect(() => { void load(); }, [load]);

  const imeiBad = touched && !isValidImei(imei);

  async function add(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!isValidImei(imei)) return;
    setBusy(true);
    try {
      await api.addDevice(nickname.trim(), model.trim(), imei);
      setNickname(""); setModel(""); setImei(""); setTouched(false);
      onToast("Phone added"); await load();
    } catch (err) { onError((err as Error).message); } finally { setBusy(false); }
  }

  async function report(d: Device) {
    try { const c = await api.openCase(d.id); onOpenCase(c.id); } catch (e) { onError((e as Error).message); }
  }
  async function remove(d: Device) {
    if (!window.confirm(`Delete ${d.nickname}? Its cases and sightings are deleted too.`)) return;
    try { await api.deleteDevice(d.id); onToast("Phone deleted"); await load(); } catch (e) { onError((e as Error).message); }
  }

  return (
    <div className="page">
      <div className="page-head"><h1>Your phones</h1></div>
      <div className="layout-devices">
        <div>
          {devices === null && <p className="muted">Loading…</p>}
          {devices?.length === 0 && (
            <div className="empty">
              <h3>No phones yet</h3>
              <p className="muted measure">Add the phone you want covered. If it ever goes missing, you can report it here and review what has been seen.</p>
            </div>
          )}
          {devices?.map((d) => {
            const active = cases.find((c) => c.device_id === d.id && ACTIVE.includes(c.state));
            const verified = d.status === "verified";
            return (
              <article className="device" key={d.id}>
                <div className="device-top">
                  <div>
                    <h3>{d.nickname}</h3>
                    <div className="device-meta num">{d.model} · IMEI {d.imei_masked}</div>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <span className={verified ? "chip" : "chip plain"}>{verified ? "Ownership confirmed" : "Not yet confirmed"}</span>
                    {d.verified_via === "demo" && <span className="chip demo">Demo check</span>}
                    {d.verified_via === "companion_app" && <span className="chip">Checked on the phone</span>}
                  </div>
                </div>
                <div className="device-actions">
                  {!verified && <VerifyBox device={d} onDone={() => { onToast("Ownership confirmed"); void load(); }} onError={onError} />}
                  {verified && active && <button className="btn" onClick={() => onOpenCase(active.id)}>Open case</button>}
                  {verified && !active && <button className="btn danger" onClick={() => report(d)}>Report as lost</button>}
                  <button className="btn ghost small" onClick={() => remove(d)}>Delete</button>
                </div>
              </article>
            );
          })}

          {cases.some((c) => !ACTIVE.includes(c.state)) && (
            <>
              <h2 style={{ margin: "28px 0 12px" }}>Past cases</h2>
              {cases.filter((c) => !ACTIVE.includes(c.state)).map((c) => (
                <div className="device" key={c.id} style={{ gridTemplateColumns: "1fr auto", alignItems: "center" }}>
                  <span>{devices?.find((d) => d.id === c.device_id)?.nickname ?? "Deleted phone"} · <span className="muted">{c.state}</span></span>
                  <button className="btn ghost small" onClick={() => onOpenCase(c.id)}>View</button>
                </div>
              ))}
            </>
          )}
        </div>

        <form className="side" onSubmit={add} noValidate>
          <h2>Add a phone</h2>
          <div className="field">
            <label htmlFor="nick">Nickname</label>
            <input id="nick" className="input" required maxLength={60} value={nickname} onChange={(e) => setNickname(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="model">Model</label>
            <input id="model" className="input" required maxLength={60} placeholder="Infinix Smart 10 HD" value={model} onChange={(e) => setModel(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="imei">IMEI</label>
            <input id="imei" className="input num" inputMode="numeric" maxLength={15} value={imei} aria-invalid={imeiBad}
              aria-describedby="imei-help" onChange={(e) => setImei(e.target.value.replace(/\D/g, ""))} onBlur={() => setTouched(true)} />
            {imeiBad
              ? <span id="imei-help" className="bad">Enter the 15 digits exactly. Check for a typo.</span>
              : <span id="imei-help" className="hint">Dial *#06# on the phone to see it. It is stored encrypted and shown masked.</span>}
          </div>
          <button className="btn" style={{ width: "100%" }} disabled={busy || !nickname.trim() || !model.trim()}>Add phone</button>
        </form>
      </div>
    </div>
  );
}
