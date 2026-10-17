import { useEffect, useState } from "react";
import { api } from "../api.js";

const usd = (v) => `$${(v ?? 0).toFixed(v >= 10 ? 2 : 3)}`;
const LABELS = {
  "openai:storyboard": ["OpenAI · GPT-4.1", "Script & storyboard"],
  "openai:image": ["OpenAI · gpt-image-1", "Scene illustrations"],
  "openai:image-cached": ["OpenAI · gpt-image-1", "Illustrations reused from cache (free)"],
  "elevenlabs:tts": ["ElevenLabs", "Voice-over (1 credit per character)"],
  "render:frames": ["Render", "Chromium + FFmpeg compute"],
};

export default function UsagePage() {
  const [days, setDays] = useState(30);
  const [r, setR] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api.usage(days).then(setR).catch((e) => setErr(e.message)); }, [days]);
  if (err) return <div className="banner error">{err}</div>;
  if (!r) return <div className="loading">Loading…</div>;
  const services = Object.entries(r.by_service);
  const days_ = Object.entries(r.by_day).slice(-14);
  const maxDay = Math.max(0.01, ...days_.map(([, v]) => v.cost_usd));
  return (
    <div className="usage">
      <header className="phead">
        <div><h1>Usage & costs</h1><div className="muted small">Provider spend and customer credits, from the ledger.</div></div>
        <div className="seg2">
          {[7, 30, 90].map((d) => <button key={d} className={days === d ? "on" : ""} onClick={() => setDays(d)}>{d} days</button>)}
        </div>
      </header>

      <div className="kpis">
        <div className="kpi"><div className="kpi-v">{usd(r.cost_usd)}</div><div className="kpi-l">Provider cost</div></div>
        <div className="kpi"><div className="kpi-v">{r.credits}</div><div className="kpi-l">Credits charged</div></div>
        <div className="kpi"><div className="kpi-v">{Object.values(r.by_theme).reduce((a, v) => a + v.videos, 0)}</div><div className="kpi-l">Videos</div></div>
        <div className="kpi"><div className="kpi-v">{r.credits ? usd(r.cost_usd / r.credits) : "—"}</div><div className="kpi-l">Cost per credit</div></div>
      </div>

      <div className="card">
        <h2>By service</h2>
        <table className="tbl">
          <thead><tr><th>Service</th><th>Used for</th><th className="num">Calls</th><th className="num">Units</th><th className="num">Cost</th></tr></thead>
          <tbody>
            {services.map(([k, v]) => (
              <tr key={k}><td><b>{LABELS[k]?.[0] || k}</b></td><td className="muted">{LABELS[k]?.[1] || ""}</td><td className="num">{v.calls}</td><td className="num">{v.units.toLocaleString()} {v.unit}</td><td className="num">{usd(v.cost_usd)}</td></tr>
            ))}
            {services.length === 0 && <tr><td colSpan={5} className="muted">No usage recorded in this period.</td></tr>}
          </tbody>
          <tfoot><tr><td colSpan={4}><b>Total</b></td><td className="num"><b>{usd(r.cost_usd)}</b></td></tr></tfoot>
        </table>
      </div>

      <div className="grid2 top">
        <div className="card">
          <h2>By theme</h2>
          <table className="tbl">
            <thead><tr><th>Theme</th><th className="num">Videos</th><th className="num">Credits</th><th className="num">Cost</th><th className="num">Cost / video</th></tr></thead>
            <tbody>
              {Object.entries(r.by_theme).map(([t, v]) => (
                <tr key={t}><td>{t}</td><td className="num">{v.videos}</td><td className="num">{v.credits}</td><td className="num">{usd(v.cost_usd)}</td><td className="num">{v.videos ? usd(v.cost_usd / v.videos) : "—"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>By day</h2>
          <div className="bars">
            {days_.map(([d, v]) => (
              <div key={d} className="barcol" title={`${d}: ${usd(v.cost_usd)} · ${v.credits} credits · ${v.videos} videos`}>
                <div className="barfill" style={{ height: `${Math.max(2, (v.cost_usd / maxDay) * 100)}%` }} />
                <div className="barlbl">{d.slice(5)}</div>
              </div>
            ))}
            {days_.length === 0 && <div className="muted small">Nothing yet.</div>}
          </div>
        </div>
      </div>

      <div className="card top">
        <h2>Rate card & credit rules</h2>
        <div className="grid2">
          <table className="tbl small">
            <tbody>{Object.entries(r.rates).map(([k, v]) => <tr key={k}><td className="mono">{k}</td><td className="num">${v}</td></tr>)}</tbody>
          </table>
          <div className="small">
            <p><b>1 credit</b> = {r.credit_rules.per_minute} finished minute in a standard theme.</p>
            <p>Premium-art themes ({r.credit_rules.premium_themes.join(", ")}) cost <b>{r.credit_rules.premium_multiplier}×</b>.</p>
            <p>Re-renders with edits charge <b>{r.credit_rules.rerender_fraction}×</b>; cached illustrations are free.</p>
            <p className="muted">Override any rate with the <span className="mono">RATE_*</span> / <span className="mono">CREDIT_*</span> environment variables.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
