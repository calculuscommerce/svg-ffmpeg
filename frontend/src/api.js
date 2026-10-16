async function j(url, opts) {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.status === 204 ? null : r.json();
}

export const api = {
  voices: () => j("/api/voices"),
  themes: () => j("/api/themes"),
  projects: () => j("/api/projects"),
  project: (id) => j(`/api/projects/${id}`),
  create: (body) => j("/api/projects", { method: "POST", body: JSON.stringify(body) }),
  remove: (id) => j(`/api/projects/${id}`, { method: "DELETE" }),
  retry: (id) => j(`/api/projects/${id}/retry`, { method: "POST" }),
  rerender: (id, storyboard) => j(`/api/projects/${id}/rerender`, { method: "POST", body: JSON.stringify(storyboard) }),
};
