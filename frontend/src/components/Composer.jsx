import { useMemo, useRef, useState } from "react";

const EXAMPLES = [
  { label: "How does a loan work?", text: "How does a loan work? Explain principal, interest rate, tenure and EMIs using Indian rupees (₹1,00,000 at 12% for 12 months) for a global audience." },
  { label: "Photosynthesis", text: "How does a plant make its own food? Explain photosynthesis for 12-year-olds: sunlight, chlorophyll, water, carbon dioxide, sugar and oxygen." },
  { label: "Phishing emails", text: "How to spot and handle a phishing email at work: warning signs, and the pause → verify → report routine." },
  { label: "Compound interest", text: "Why compound interest is called the eighth wonder of the world. Show how ₹10,000 grows at 10% per year over 10, 20 and 30 years." },
  { label: "How vaccines work", text: "How vaccines train the immune system: antigens, antibodies, memory cells, and why herd immunity matters." },
];

const DURATIONS = [
  { v: 30, label: "30 sec", hint: "3–4 scenes · quick explainer" },
  { v: 60, label: "1 min", hint: "6–7 scenes · full concept" },
  { v: 300, label: "5 min", hint: "18–22 scenes · deep dive" },
];

export default function Composer({ voices, themes, onCreate }) {
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(60);
  const [voice, setVoice] = useState("");
  const [theme, setTheme] = useState("auto");
  const [captions, setCaptions] = useState(false);
  const [hd, setHd] = useState(false);
  const [hand, setHand] = useState(false);
  const [language, setLanguage] = useState("English");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const audioRef = useRef(null);

  const voiceList = useMemo(() => {
    const pref = ["Sarah", "Rachel", "Matilda", "Alice", "Brian", "Daniel", "George", "Charlotte"];
    return [...voices].sort((a, b) => (pref.indexOf(a.name) + 1 || 99) - (pref.indexOf(b.name) + 1 || 99));
  }, [voices]);

  const words = prompt.trim().split(/\s+/).filter(Boolean).length;

  function preview(v) {
    if (!v?.preview_url) return;
    if (audioRef.current) audioRef.current.pause();
    audioRef.current = new Audio(v.preview_url);
    audioRef.current.play();
  }

  async function submit(e) {
    e.preventDefault();
    if (prompt.trim().length < 3) return;
    setBusy(true); setErr(null);
    try {
      await onCreate({ prompt, duration, voice_id: voice || null, theme, captions, hd, language, hand });
    } catch (e2) {
      setErr(e2.message); setBusy(false);
    }
  }

  return (
    <div className="composer">
      <header className="hero">
        <h1>Turn any topic into an animated explainer</h1>
        <p className="lead">Paste a topic, notes or an article. We write the script, voice it, and animate a hand-drawn whiteboard video — no video model involved.</p>
      </header>

      <form onSubmit={submit} className="card form">
        <label className="label">What should the video explain?</label>
        <textarea
          className="textarea"
          rows={7}
          placeholder="e.g. How does a loan work? Explain principal, interest and EMIs with an example in rupees…  — or paste your own content and we'll stay faithful to it."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div className="row between small muted">
          <span>{words} words {words > 1500 ? "· long content will be summarised" : ""}</span>
          <span className="chips">
            {EXAMPLES.map((ex) => (
              <button type="button" key={ex.label} className="chip" onClick={() => setPrompt(ex.text)}>{ex.label}</button>
            ))}
          </span>
        </div>

        <div className="grid2">
          <div>
            <label className="label">Length</label>
            <div className="seg">
              {DURATIONS.map((d) => (
                <button type="button" key={d.v} className={"seg-btn " + (duration === d.v ? "on" : "")} onClick={() => setDuration(d.v)}>
                  <div className="seg-label">{d.label}</div>
                  <div className="seg-hint">{d.hint}</div>
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label">Voice</label>
            <div className="row gap">
              <select className="select" value={voice} onChange={(e) => setVoice(e.target.value)}>
                <option value="">Auto (recommended)</option>
                {voiceList.map((v) => (
                  <option key={v.voice_id} value={v.voice_id}>
                    {v.name}{v.accent ? ` · ${v.accent}` : ""}{v.gender ? ` · ${v.gender}` : ""}
                  </option>
                ))}
              </select>
              <button type="button" className="btn ghost" disabled={!voice} onClick={() => preview(voices.find((v) => v.voice_id === voice))}>▶ Preview</button>
            </div>
            <label className="label top">Language</label>
            <select className="select" value={language} onChange={(e) => setLanguage(e.target.value)}>
              {["English", "Hindi", "Tamil", "Spanish", "French", "German", "Portuguese", "Arabic", "Japanese"].map((l) => <option key={l}>{l}</option>)}
            </select>
          </div>
        </div>

        <div className="grid2">
          <div>
            <label className="label">Colour theme</label>
            <div className="swatches">
              <button type="button" className={"swatch auto " + (theme === "auto" ? "on" : "")} onClick={() => setTheme("auto")} title="Let the AI pick">Auto</button>
              {themes.map((t) => (
                <button type="button" key={t.name} className={"swatch " + (theme === t.name ? "on" : "")} onClick={() => setTheme(t.name)} title={t.name}
                  style={{ background: t.mono ? `linear-gradient(135deg, #111 0 50%, #fff 50% 100%)` : `linear-gradient(135deg, ${t.primary} 0 50%, ${t.accent} 50% 100%)`, border: t.mono ? "1px solid #999" : undefined }} />
              ))}
            </div>
          </div>
          <div className="toggles">
            <label className="toggle"><input type="checkbox" checked={hand} onChange={(e) => setHand(e.target.checked)} /> Drawing hand on screen <span className="muted small">(whiteboard style — pairs well with the black “marker” theme)</span></label>
            <label className="toggle"><input type="checkbox" checked={captions} onChange={(e) => setCaptions(e.target.checked)} /> Burn in captions</label>
            <label className="toggle"><input type="checkbox" checked={hd} onChange={(e) => setHd(e.target.checked)} /> 1080p (slower render)</label>
          </div>
        </div>

        {err && <div className="banner error">{err}</div>}
        <div className="row between">
          <span className="small muted">Typical time: 30 s video ≈ 1 min · 1 min ≈ 2 min · 5 min ≈ 10 min</span>
          <button className="btn primary lg" disabled={busy || prompt.trim().length < 3}>{busy ? "Starting…" : "Generate video"}</button>
        </div>
      </form>

      <section className="how">
        {[
          ["1", "Script", "An LLM writes narration and a structured storyboard from your content."],
          ["2", "Voice", "ElevenLabs narrates it and returns word timestamps."],
          ["3", "Animate", "Scenes are laid out from hand-drawn SVG templates, timed to the words."],
          ["4", "Render", "Headless Chromium + FFmpeg produce a crisp MP4 in minutes."],
        ].map(([n, t, d]) => (
          <div className="how-step" key={n}><div className="how-n">{n}</div><div><b>{t}</b><div className="small muted">{d}</div></div></div>
        ))}
      </section>
    </div>
  );
}
