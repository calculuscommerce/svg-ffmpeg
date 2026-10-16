from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from . import jobs, llm, tts  # noqa: E402
from .models import CreateProject, Storyboard  # noqa: E402
from .themes import THEMES  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(jobs.worker())
    yield
    task.cancel()


app = FastAPI(title="Whiteboard video generator", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/media", StaticFiles(directory=str(jobs.DATA)), name="media")


def _summary(p: dict) -> dict:
    return {k: p.get(k) for k in ("id", "title", "status", "progress", "message", "created_at", "duration", "video_url")} | {
        "input": {"duration": p["input"]["duration"], "prompt": p["input"]["prompt"][:120]}}


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/voices")
async def voices():
    try:
        return await tts.list_voices()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"ElevenLabs: {e}")


@app.get("/api/themes")
async def themes():
    return [{"name": k, **v} for k, v in THEMES.items()]


@app.get("/api/assets")
async def assets():
    return llm.asset_names()


@app.get("/api/projects")
async def list_projects():
    ps = sorted(jobs.store.projects.values(), key=lambda p: p["created_at"], reverse=True)
    return [_summary(p) for p in ps]


@app.post("/api/projects", status_code=201)
async def create_project(inp: CreateProject):
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
    q = jobs.store.create(CreateProject(**p["input"]), storyboard)
    await jobs.queue.put(q["id"])
    return q
