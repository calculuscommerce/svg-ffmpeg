import { useEffect, useMemo, useRef, useState } from "react";

const PREF = ["Sarah", "Rachel", "Matilda", "Alice", "Brian", "Daniel", "George", "Charlotte", "Eric", "River"];

export default function VoicePicker({ voices, value, onChange }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [playing, setPlaying] = useState(null);
  const audioRef = useRef(null);
  const boxRef = useRef(null);

  const list = useMemo(() => {
    const sorted = [...voices].sort((a, b) => (PREF.indexOf(a.name) + 1 || 99) - (PREF.indexOf(b.name) + 1 || 99));
    return sorted.filter((v) => !q || `${v.name} ${v.accent || ""} ${v.gender || ""} ${v.description || ""}`.toLowerCase().includes(q.toLowerCase()));
  }, [voices, q]);

  const selected = voices.find((v) => v.voice_id === value);

  useEffect(() => {
    const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function toggle(e, v) {
    e.stopPropagation();
    if (playing === v.voice_id) { audioRef.current?.pause(); setPlaying(null); return; }
    audioRef.current?.pause();
    const a = new Audio(v.preview_url);
    a.onended = () => setPlaying(null);
    a.play().catch(() => {});
    audioRef.current = a;
    setPlaying(v.voice_id);
  }

  return (
    <div className="voice-box" ref={boxRef}>
      <button type="button" className="voice-current" onClick={() => setOpen((o) => !o)}>
        <span className="voice-avatar">{selected ? selected.name[0] : "✦"}</span>
        <span className="voice-main">
          <b>{selected ? selected.name : "Auto voice"}</b>
          <span className="muted small">{selected ? [selected.gender, selected.accent, selected.description].filter(Boolean).join(" · ") : "We pick a clear narrator for you"}</span>
        </span>
        <span className="muted">▾</span>
      </button>
      {open && (
        <div className="voice-pop">
          <input className="input sm" placeholder="Search voices…" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
          <div className="voice-list">
            <div className={"voice-row " + (!value ? "on" : "")} onClick={() => { onChange(""); setOpen(false); }}>
              <span className="voice-avatar">✦</span>
              <span className="voice-main"><b>Auto</b><span className="muted small">Recommended narrator</span></span>
            </div>
            {list.map((v) => (
              <div key={v.voice_id} className={"voice-row " + (value === v.voice_id ? "on" : "")} onClick={() => { onChange(v.voice_id); setOpen(false); }}>
                <span className="voice-avatar">{v.name[0]}</span>
                <span className="voice-main">
                  <b>{v.name}</b>
                  <span className="muted small">{[v.gender, v.accent, v.description].filter(Boolean).join(" · ")}</span>
                </span>
                {v.preview_url && (
                  <button type="button" className={"play " + (playing === v.voice_id ? "on" : "")} onClick={(e) => toggle(e, v)} title="Preview">
                    {playing === v.voice_id ? "■" : "▶"}
                  </button>
                )}
              </div>
            ))}
            {list.length === 0 && <div className="muted small pad">No voices match.</div>}
          </div>
        </div>
      )}
    </div>
  );
}
