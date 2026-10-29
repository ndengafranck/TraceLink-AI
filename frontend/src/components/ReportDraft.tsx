import { useEffect, useState } from "react";
import { api, type Audience, type Lang, type ReportDraft as Draft } from "../api";
import { PANEL, REASONS } from "./i18n";

export function ReportDraftPanel({ caseId, lang, canDraft, onError }: {
  caseId: string; lang: Lang; canDraft: boolean; onError: (m: string) => void;
}) {
  const t = PANEL[lang];
  const [audience, setAudience] = useState<Audience>("police");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => { setDraft(null); setText(""); }, [lang, audience]);

  async function write() {
    setBusy(true);
    try { const d = await api.reportDraft(caseId, lang, audience); setDraft(d); setText(d.body); }
    catch (e) { onError((e as Error).message); } finally { setBusy(false); }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1800); }
    catch { onError("Copy failed. Select the text and copy it by hand."); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = `tracelink-${audience}-${lang}.txt`; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="draft" aria-labelledby="draft-h" lang={lang}>
      <div className="topline">
        <div>
          <h2 id="draft-h">{t.r_title}</h2>
          <p className="muted measure" style={{ marginTop: 6 }}>{t.r_intro}</p>
        </div>
        <div className="panel-actions">
          <div className="seg light" role="group" aria-label={t.r_audience}>
            <button className={audience === "police" ? "on" : ""} aria-pressed={audience === "police"} onClick={() => setAudience("police")}>{t.r_police}</button>
            <button className={audience === "operator" ? "on" : ""} aria-pressed={audience === "operator"} onClick={() => setAudience("operator")}>{t.r_operator}</button>
          </div>
          <button className="btn" onClick={write} disabled={busy || !canDraft}>{busy ? t.r_busy : draft ? t.r_again : t.r_write}</button>
        </div>
      </div>
      {draft && (
        <div className="reveal">
          <div className="draft-meta">
            <span className={draft.source === "ai" ? "chip" : "chip plain"}>
              {draft.source === "ai" ? `${t.writtenBy} (${draft.model})` : t.standard}
            </span>
            {draft.source === "fallback" && draft.fallback_reason && (
              <span className="muted">{REASONS[lang][draft.fallback_reason] ?? draft.fallback_reason}</span>
            )}
          </div>
          <label className="sr" htmlFor="draft-text">{draft.title}</label>
          <textarea id="draft-text" className="draft-text" value={text} onChange={(e) => setText(e.target.value)} rows={20} />
          <p className="muted" style={{ fontSize: ".9rem", margin: "8px 0 12px" }}>{t.r_imei}</p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="btn small" onClick={copy}>{copied ? t.r_copied : t.r_copy}</button>
            <button className="btn small ghost" onClick={download}>{t.r_download}</button>
          </div>
        </div>
      )}
    </section>
  );
}
