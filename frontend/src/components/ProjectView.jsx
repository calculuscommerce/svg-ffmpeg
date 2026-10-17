import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";

const STAGES = [
  ["writing", "Script"],
  ["voicing", "Voice-over"],
  ["composing", "Layout"],
  ["rendering", "Render"],
];

export default function ProjectView({ id, onChanged, onOpen }) {
  const [p, setP] = useState(null);
  const [err, setErr] = useState(null);
  const [edit, setEdit] = useState(null); // edited storyboard copy
  const [sel, setSel] = useState(0);
  const videoRef = useRef(null);

  useEffect(() => {
    let alive = true;
    setP(null); setEdit(null); setSel(0);
    async function load() {
      try {
        const d = await api.project(id);
        if (!alive) return;
        setP(d);
        if (!["done", "error"].includes(d.status)) setTimeout(load, 1500);
        else onChanged();
      } catch (e) { if (alive) setErr(e.message); }
    }
    load();
    return () => { alive = false; };
  }, [id]); // eslint-disable-line

  const sb = edit || p?.storyboard;
  const running = p && !["done", "error"].includes(p.status);
  const stageIdx = p ? STAGES.findIndex(([k]) => k === p.status) : -1;

  const dirty = useMemo(() => edit && JSON.stringify(edit) !== JSON.stringify(p?.storyboard), [edit, p]);

  function updateScene(i, patch) {
    const base = edit || structuredClone(p.storyboard);
    base.scenes[i] = { ...base.scenes[i], ...patch };
    setEdit(base);
  }

  async function rerender() {
    const q = await api.rerender(id, edit);
    onChanged();
    onOpen(q.id);
  }

  function seekTo(t) {
    if (videoRef.current) { videoRef.current.currentTime = t + 0.05; videoRef.current.play(); }
  }

  if (err) return <div className="banner error">{err}</div>;
  if (!p) return <div className="loading">Loading…</div>;

  return (
    <div className="project">
      <header className="phead">
        <div>
          <h1>{p.title || "Generating…"}</h1>
          <div className="muted small">
            {p.input.duration === 300 ? "5 min" : p.input.duration === 60 ? "1 min" : "30 s"} target
            {p.duration ? ` · ${p.duration}s rendered` : ""} · theme {sb?.theme || "auto"} · {new Date(p.created_at * 1000).toLocaleString()}
          </div>
        </div>
        <div className="row gap">
          {p.status === "error" && <button className="btn" onClick={async () => { const q = await api.retry(id); onChanged(); onOpen(q.id); }}>Retry</button>}
          {p.video_url && <a className="btn primary" href={p.video_url} download={`${(p.title || "video").replace(/[^\w]+/g, "-")}.mp4`}>Download MP4</a>}
          {p.captions_url && p.status === "done" && <a className="btn ghost" href={p.captions_url} download>Captions .srt</a>}
        </div>
      </header>

      {running && (
        <div className="card progress">
          <div className="stages">
            {STAGES.map(([k, label], i) => (
              <div key={k} className={"stage " + (i < stageIdx ? "done" : i === stageIdx ? "on" : "")}>
                <div className="stage-dot">{i < stageIdx ? "✓" : i + 1}</div>
                <div>{label}</div>
              </div>
            ))}
          </div>
          <div className="bar"><div className="bar-fill" style={{ width: `${p.progress}%` }} /></div>
          <div className="row between small muted"><span>{p.message}</span><span>{p.progress}%</span></div>
        </div>
      )}

      {p.status === "error" && (
        <div className="banner error">
          <b>Generation failed.</b> {p.error}
        </div>
      )}

      {p.video_url && (
        <div className="player card">
          <video ref={videoRef} src={p.video_url} controls playsInline poster={p.scenes?.[0]?.thumb_url} />
        </div>
      )}

      {sb && (
        <section className="scenes">
          <div className="row between">
            <h2>Storyboard · {sb.scenes.length} scenes</h2>
            {dirty && <button className="btn primary" onClick={rerender}>Re-voice & re-render with edits</button>}
          </div>
          <div className="strip">
            {sb.scenes.map((s, i) => {
              const meta = p.scenes?.[i];
              return (
                <div key={i} className={"thumb " + (sel === i ? "on" : "")} onClick={() => { setSel(i); if (meta && p.video_url) seekTo(meta.start); }}>
                  {meta?.thumb_url ? <img src={meta.thumb_url + (running ? `?t=${p.progress}` : "")} alt="" onError={(e) => { e.target.style.visibility = "hidden"; }} /> : <div className="thumb-ph">{s.type}</div>}
                  <div className="thumb-cap"><span className="tag">{s.type}</span> {s.heading || "—"}</div>
                </div>
              );
            })}
          </div>

          {sb.scenes[sel] && (
            <div className="card editor">
              <div className="row between">
                <div className="row gap"><span className="tag big">{sb.scenes[sel].type}</span><b>Scene {sel + 1}</b>{p.scenes?.[sel] && <span className="muted small">{p.scenes[sel].duration}s</span>}</div>
                {running && <span className="muted small">Edits apply to a new render after this one finishes</span>}
              </div>
              <label className="label">Heading</label>
              <input className="input" value={sb.scenes[sel].heading || ""} onChange={(e) => updateScene(sel, { heading: e.target.value })} />
              <label className="label">Narration</label>
              <textarea className="textarea" rows={4} value={sb.scenes[sel].narration} onChange={(e) => updateScene(sel, { narration: e.target.value })} />
              {sb.scenes[sel].items?.length > 0 && (
                <>
                  <label className="label">On-screen items</label>
                  <div className="items">
                    {sb.scenes[sel].items.map((it, k) => (
                      <div className="item" key={k}>
                        <span className="muted small mono">{it.icon || "·"}</span>
                        <input className="input sm" value={it.label || ""} placeholder="label" onChange={(e) => { const items = sb.scenes[sel].items.map((x, j) => j === k ? { ...x, label: e.target.value } : x); updateScene(sel, { items }); }} />
                        <input className="input sm" value={it.value || ""} placeholder="value" onChange={(e) => { const items = sb.scenes[sel].items.map((x, j) => j === k ? { ...x, value: e.target.value } : x); updateScene(sel, { items }); }} />
                        <input className="input sm wide" value={it.caption || ""} placeholder="caption" onChange={(e) => { const items = sb.scenes[sel].items.map((x, j) => j === k ? { ...x, caption: e.target.value } : x); updateScene(sel, { items }); }} />
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </section>
      )}

      {p.usage && Object.keys(p.usage.lines || {}).length > 0 && (
        <div className="card top cost">
          <div className="row between">
            <h2>Cost of this video</h2>
            <div className="row gap"><span className="tag big">{p.usage.credits} credits</span><b>${p.usage.cost_usd.toFixed(3)} provider cost</b></div>
          </div>
          <table className="tbl small">
            <thead><tr><th>Service</th><th className="num">Calls</th><th className="num">Units</th><th className="num">Cost</th></tr></thead>
            <tbody>
              {Object.entries(p.usage.lines).map(([k, v]) => (
                <tr key={k}><td>{{ "openai:storyboard": "GPT-4.1 storyboard", "openai:image": "gpt-image-1 illustrations", "openai:image-cached": "Illustrations from cache", "elevenlabs:tts": "ElevenLabs voice-over", "render:frames": "Render" }[k] || k}</td>
                  <td className="num">{v.calls}</td><td className="num">{v.units.toLocaleString()} {v.unit}</td><td className="num">${v.cost_usd.toFixed(4)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {p.log?.length > 0 && (
        <details className="log">
          <summary className="small muted">Activity log</summary>
          <pre>{p.log.map((l) => `${new Date(l.t * 1000).toLocaleTimeString()}  ${l.m}`).join("\n")}</pre>
        </details>
      )}
    </div>
  );
}
