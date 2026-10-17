from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from . import jobs, ledger, llm, thumbs, tts  # noqa: E402
from .models import CreateProject, Storyboard  # noqa: E402
from .themes import GALLERY, THEMES  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(jobs.worker())
    thumb_task = asyncio.create_task(thumbs.ensure_thumbs())
    yield
    task.cancel(); thumb_task.cancel()


app = FastAPI(title="Whiteboard video generator", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/media", StaticFiles(directory=str(jobs.DATA)), name="media")
thumbs.OUT.mkdir(parents=True, exist_ok=True)
app.mount("/themes", StaticFiles(directory=str(thumbs.OUT)), name="themes")


def _summary(p: dict) -> dict:
    return {k: p.get(k) for k in ("id", "title", "status", "progress", "message", "created_at", "duration", "video_url", "usage")} | {
        "input": {"duration": p["input"]["duration"], "prompt": (p["input"].get("script") or p["input"].get("prompt") or "")[:120]}}


@app.get("/api/health")
async def health():
    return {"ok": True}


_voices_cache: dict = {}


@app.get("/api/voices")
async def voices():
    import time
    if _voices_cache.get("at", 0) > time.time() - 600:
        return _voices_cache["v"]
    try:
        v = await tts.list_voices()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"ElevenLabs: {e}")
    _voices_cache.update(v=v, at=time.time())
    return v


@app.get("/api/themes")
async def themes():
    try:
        await thumbs.ensure_thumbs()
    except Exception:  # noqa: BLE001
        pass
    return [{**THEMES[n], "thumb_url": f"/themes/{n}.png" if thumbs.thumb_path(n).exists() else None} for n in GALLERY]


@app.get("/api/assets")
async def assets():
    return llm.asset_names()


@app.get("/api/projects")
async def list_projects():
    ps = sorted(jobs.store.projects.values(), key=lambda p: p["created_at"], reverse=True)
    return [_summary(p) for p in ps]


@app.post("/api/projects", status_code=201)
async def create_project(inp: CreateProject):
    if inp.mode == "script" and not (inp.script or "").strip():
        raise HTTPException(422, "script is required in own-script mode")
    if inp.mode == "prompt" and len(inp.prompt.strip()) < 3:
        raise HTTPException(422, "prompt is too short")
    p = jobs.store.create(inp)
    await jobs.queue.put(p["id"])
    return p


@app.get("/api/projects/{pid}")
async def get_project(pid: str):
    p = jobs.store.projects.get(pid)
    if not p:
        raise HTTPException(404)
    return p


@app.delete("/api/projects/{pid}", status_code=204)
async def delete_project(pid: str):
    jobs.store.delete(pid)


@app.post("/api/projects/{pid}/retry", status_code=201)
async def retry(pid: str):
    p = jobs.store.projects.get(pid)
    if not p:
        raise HTTPException(404)
    q = jobs.store.create(CreateProject(**p["input"]))
    await jobs.queue.put(q["id"])
    return q


@app.post("/api/projects/{pid}/rerender", status_code=201)
async def rerender(pid: str, storyboard: Storyboard):
    """Re-voice and re-render with an edited storyboard (skips the LLM)."""
    p = jobs.store.projects.get(pid)
    if not p:
        raise HTTPException(404)
    q = jobs.store.create(CreateProject(**p["input"]), storyboard, rerender_of=pid)
    await jobs.queue.put(q["id"])
    return q


@app.get("/api/usage")
async def usage(days: int = 30):
    import time
    since = time.time() - days * 86400
    return ledger.usage_report(since=since, projects=jobs.store.projects)


@app.get("/api/usage/estimate")
async def estimate(duration: int = 60, theme: str = "hand-drawn", visuals: str = "illustrated"):
    """Pre-generation estimate shown in the composer."""
    scenes = {30: 4, 60: 7, 300: 20}.get(duration, round(duration / 9))
    T = THEMES.get(theme, THEMES["hand-drawn"])
    from .themes import IMAGE_OPTS
    q = (IMAGE_OPTS.get(theme) or {}).get("quality") or "medium"
    img_tokens = {"low": 400, "medium": 1570, "high": 6200}.get(q, 1570)
    n_images = 0 if (visuals != "illustrated" or T.get("no_images")) else round(scenes * 0.75)
    chars = {30: 400, 60: 870, 300: 4100}.get(duration, duration * 14)
    llm_cost = ledger.cost_llm("gpt-4.1", 2500, {30: 1200, 60: 2000, 300: 6000}.get(duration, duration * 20)) * 1.3
    return {"duration": duration, "theme": theme, "scenes": scenes, "images": n_images, "image_quality": q,
            "cost": {"openai_llm": round(llm_cost, 4), "elevenlabs": round(ledger.cost_tts(chars), 4),
                     "openai_images": round(n_images * ledger.cost_image(img_tokens, 60), 4), "render": round(ledger.cost_render(duration * 1.1), 4)},
            "cost_total_usd": round(llm_cost + ledger.cost_tts(chars) + n_images * ledger.cost_image(img_tokens, 60) + ledger.cost_render(duration * 1.1), 4),
            "credits": ledger.video_credits(duration, theme)}
