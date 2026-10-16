function fmtAgo(ts) {
  const s = Math.max(0, (Date.now() / 1000 - ts) | 0);
  if (s < 60) return "just now";
  if (s < 3600) return `${(s / 60) | 0} min ago`;
  if (s < 86400) return `${(s / 3600) | 0} h ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

const DUR = { 30: "30 s", 60: "1 min", 300: "5 min" };

export default function Sidebar({ projects, selected, onSelect, onNew, onDelete }) {
  return (
    <aside className="sidebar">
      <div className="brand" onClick={onNew}>
        <span className="brand-mark">✎</span>
        <span className="brand-name">Sketchboard</span>
      </div>
      <button className="btn primary block" onClick={onNew}>+ New video</button>
      <div className="side-title">Your videos</div>
      <div className="plist">
        {projects.length === 0 && <div className="muted small pad">Nothing yet. Generate your first video.</div>}
        {projects.map((p) => (
          <div key={p.id} className={"pitem " + (selected === p.id ? "active" : "")} onClick={() => onSelect(p.id)}>
            <div className={"dot " + p.status} title={p.status} />
            <div className="pinfo">
              <div className="ptitle">{p.title || (p.input.prompt || "").slice(0, 48) || "Untitled"}</div>
              <div className="pmeta">
                {DUR[p.input.duration]} · {p.status === "done" ? `${p.duration}s` : p.status === "error" ? "failed" : `${p.progress}%`} · {fmtAgo(p.created_at)}
              </div>
            </div>
            <button className="icon-btn" title="Delete" onClick={(e) => { e.stopPropagation(); onDelete(p.id); }}>×</button>
          </div>
        ))}
      </div>
    </aside>
  );
}
