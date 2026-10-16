import { useEffect, useMemo, useState } from "react";

function Tile({ t, selected, onSelect, large }) {
  return (
    <button type="button" className={"theme-tile " + (selected ? "on" : "") + (large ? " large" : "")} onClick={() => onSelect(t.name)} title={t.description}>
      <div className="theme-thumb" style={{ background: t.bg }}>
        {t.thumb_url ? <img src={t.thumb_url} alt="" loading="lazy" /> : (
          <div className="theme-swatch" style={{ background: `linear-gradient(135deg, ${t.primary} 0 50%, ${t.accent} 50% 100%)` }} />
        )}
      </div>
      <div className="theme-cap">
        <span>{t.title}</span>
        {selected && <span className="theme-check">✓</span>}
      </div>
    </button>
  );
}

export function ThemeStrip({ themes, value, onChange, onSeeAll }) {
  // show the selected one first, then the first few
  const shown = useMemo(() => {
    const sel = themes.find((t) => t.name === value);
    const rest = themes.filter((t) => t.name !== value);
    return [sel, ...rest].filter(Boolean).slice(0, 4);
  }, [themes, value]);
  return (
    <div className="theme-section">
      <div className="row between">
        <label className="label">Visual style</label>
        <button type="button" className="link" onClick={onSeeAll}>⊞ See all themes</button>
      </div>
      <div className="theme-strip">
        {shown.map((t) => <Tile key={t.name} t={t} selected={t.name === value} onSelect={onChange} large />)}
      </div>
    </div>
  );
}

export function ThemeModal({ themes, value, onChange, onClose }) {
  const [q, setQ] = useState("");
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const list = themes.filter((t) => !q || (t.title + " " + t.description).toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h2>Choose a theme</h2>
            <div className="muted small">Pick the visual language for this video.</div>
          </div>
          <button type="button" className="icon-btn big" onClick={onClose}>×</button>
        </div>
        <input className="input" placeholder="Search themes…" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
        <div className="theme-grid">
          {list.map((t) => <Tile key={t.name} t={t} selected={t.name === value} onSelect={(n) => { onChange(n); onClose(); }} />)}
        </div>
      </div>
    </div>
  );
}
