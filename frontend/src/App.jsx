import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import Composer from "./components/Composer.jsx";
import ProjectView from "./components/ProjectView.jsx";
import Sidebar from "./components/Sidebar.jsx";

export default function App() {
  const [projects, setProjects] = useState([]);
  const [selected, setSelected] = useState(null);
  const [voices, setVoices] = useState([]);
  const [themes, setThemes] = useState([]);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try { setProjects(await api.projects()); } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => {
    refresh();
    api.voices().then(setVoices).catch(() => setVoices([]));
    api.themes().then(setThemes).catch(() => {});
  }, [refresh]);

  // poll the list while anything is in progress
  useEffect(() => {
    const busy = projects.some((p) => !["done", "error"].includes(p.status));
    if (!busy) return;
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
  }, [projects, refresh]);

  async function onCreate(body) {
    setError(null);
    const p = await api.create(body);
    await refresh();
    setSelected(p.id);
  }

  async function onDelete(id) {
    await api.remove(id);
    if (selected === id) setSelected(null);
    refresh();
  }

  return (
    <div className="app">
      <Sidebar projects={projects} selected={selected} onSelect={setSelected} onNew={() => setSelected(null)} onDelete={onDelete} />
      <main className="main">
        {error && <div className="banner error">{error}</div>}
        {selected ? (
          <ProjectView
            id={selected}
            voices={voices}
            onChanged={refresh}
            onOpen={setSelected}
          />
        ) : (
          <Composer voices={voices} themes={themes} onCreate={onCreate} />
        )}
      </main>
    </div>
  );
}
