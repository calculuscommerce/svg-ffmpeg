import { useState } from "react";
import { ThemeModal, ThemeStrip } from "./ThemePicker.jsx";
import VoicePicker from "./VoicePicker.jsx";

const EXAMPLES = [
  { label: "How does a loan work?", text: "How does a loan work? Explain principal, interest rate, tenure and EMIs using Indian rupees (₹1,00,000 at 12% for 12 months) for a global audience." },
  { label: "Photosynthesis", text: "How does a plant make its own food? Explain photosynthesis for 12-year-olds: sunlight, chlorophyll, water, carbon dioxide, sugar and oxygen." },
  { label: "Phishing emails", text: "How to spot and handle a phishing email at work: warning signs, and the pause → verify → report routine." },
  { label: "Compound interest", text: "Why compound interest is called the eighth wonder of the world. Show how ₹10,000 grows at 10% per year over 10, 20 and 30 years." },
];

const DURATIONS = [
  { v: 30, label: "30 sec", hint: "3–4 scenes", words: 72 },
  { v: 60, label: "1 min", hint: "6–7 scenes", words: 150 },
  { v: 300, label: "5 min", hint: "18–22 scenes", words: 760 },
];
const LANGS = ["English", "Hindi", "Tamil", "Spanish", "French", "German", "Portuguese", "Arabic", "Japanese"];

export default function Composer({ voices, themes, onCreate }) {
  const [mode, setMode] = useState("prompt");
  const [prompt, setPrompt] = useState("");
  const [script, setScript] = useState("");
  const [duration, setDuration] = useState(60);
  const [voice, setVoice] = useState("");
  const [theme, setTheme] = useState("hand-drawn");
  const [language, setLanguage] = useState("English");
  const [captions, setCaptions] = useState(false);
  const [hd, setHd] = useState(false);
  const [hand, setHand] = useState(false);
  const [visuals, setVisuals] = useState("illustrated");
  const [showThemes, setShowThemes] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const dur = DURATIONS.find((d) => d.v === duration);
  const scriptWords = script.trim().split(/\s+/).filter(Boolean).length;
  const ready = mode === "prompt" ? prompt.trim().length >= 3 : scriptWords >= 5;
  const themeObj = themes.find((t) => t.name === theme);

  async function submit(e) {
    e.preventDefault();
    if (!ready) return;
    setBusy(true); setErr(null);
    try {
      await onCreate({ mode, prompt, script: mode === "script" ? script : null, duration, voice_id: voice || null, theme, captions, hd, language, hand, visuals });
    } catch (e2) { setErr(e2.message); setBusy(false); }
  }

  return (
    <div className="composer">
      <header className="hero">
        <h1>What video do you want to create?</h1>
      </header>

      <form onSubmit={submit}>
        <div className="mode-row">
          <div className="seg2">
            <button type="button" className={mode === "prompt" ? "on" : ""} onClick={() => setMode("prompt")}>Prompt</button>
            <button type="button" className={mode === "script" ? "on" : ""} onClick={() => setMode("script")}>Own Script</button>
          </div>
          <span className="muted small">{mode === "prompt" ? "We write the script from your topic or notes." : "Your script is narrated exactly as written; we only design the visuals."}</span>
        </div>

        <div className="card compose-card">
          <label className="label top0">{mode === "prompt" ? "Topic or source content" : "Video instructions"}</label>
          <textarea className="textarea plain" rows={mode === "prompt" ? 6 : 3}
            placeholder={mode === "prompt" ? "e.g. How does a loan work? Explain principal, interest and EMIs with an example in rupees…  — or paste an article and we'll stay faithful to it."
                                         : "Describe the visuals, audience, style, and any instructions for the video (optional)."}
            value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          {mode === "prompt" && (
            <div className="chips">
              {EXAMPLES.map((ex) => <button type="button" key={ex.label} className="chip" onClick={() => setPrompt(ex.text)}>{ex.label}</button>)}
            </div>
          )}
          <div className="opts-row">
            <select className="pill" value={duration} onChange={(e) => setDuration(Number(e.target.value))} title="Length">
              {DURATIONS.map((d) => <option key={d.v} value={d.v}>⏱ {d.label}</option>)}
            </select>
            <span className="pill static">▭ 16:9</span>
            <select className="pill" value={language} onChange={(e) => setLanguage(e.target.value)} title="Language">
              {LANGS.map((l) => <option key={l}>🌐 {l}</option>)}
            </select>
            <select className="pill" value={visuals} onChange={(e) => setVisuals(e.target.value)} title="Visuals">
              <option value="illustrated">✦ Illustrated</option>
              <option value="diagram">▤ Diagram only</option>
            </select>
            <label className="pill check"><input type="checkbox" checked={hand} onChange={(e) => setHand(e.target.checked)} /> ✍ Drawing hand</label>
            <label className="pill check"><input type="checkbox" checked={captions} onChange={(e) => setCaptions(e.target.checked)} /> Captions</label>
            <label className="pill check"><input type="checkbox" checked={hd} onChange={(e) => setHd(e.target.checked)} /> 1080p</label>
          </div>
        </div>

        {mode === "script" && (
          <div className="card compose-card script-card">
            <label className="label top0">Script</label>
            <textarea className="textarea plain" rows={9} placeholder="Enter your script. It will be narrated exactly as written." value={script} onChange={(e) => setScript(e.target.value)} />
            <div className="row between small muted">
              <span>Around {dur.words} words fits the selected duration; longer scripts simply make a longer video.</span>
              <span className={scriptWords > dur.words * 1.3 ? "warn" : ""}>{scriptWords} / {dur.words}</span>
            </div>
          </div>
        )}

        <div className="grid2 top">
          <ThemeStrip themes={themes} value={theme} onChange={setTheme} onSeeAll={() => setShowThemes(true)} />
          <div>
            <label className="label">Voice</label>
            <VoicePicker voices={voices} value={voice} onChange={setVoice} />
            {themeObj?.hand === "none" && hand && <div className="small muted top">The {themeObj.title} theme has no drawing hand; the toggle is ignored.</div>}
          </div>
        </div>

        {err && <div className="banner error">{err}</div>}
        <div className="row between top">
          <span className="small muted">Typical time: 30 s ≈ 1 min · 1 min ≈ 2 min · 5 min ≈ 10 min</span>
          <button className="btn primary lg" disabled={busy || !ready}>{busy ? "Starting…" : "Generate video"}</button>
        </div>
      </form>

      {showThemes && <ThemeModal themes={themes} value={theme} onChange={setTheme} onClose={() => setShowThemes(false)} />}
    </div>
  );
}
