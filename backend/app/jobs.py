"""Project store + background pipeline: script -> voice -> compose -> render."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from . import compose, images, llm, tts
from .models import CreateProject, Storyboard
from .templates import ILLUSTRATED
from .themes import player_theme, theme as get_theme

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "projects"
DATA.mkdir(parents=True, exist_ok=True)

STAGES = ["queued", "writing", "voicing", "composing", "rendering", "done", "error"]


class Store:
    def __init__(self):
        self.projects: dict[str, dict] = {}
        for f in sorted(DATA.glob("*/project.json")):
            try:
                p = json.loads(f.read_text())
                if p["status"] not in ("done", "error"):
                    p["status"], p["error"] = "error", "server restarted during generation"
                self.projects[p["id"]] = p
            except Exception:
                pass

    def save(self, p: dict):
        d = DATA / p["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=1))

    def create(self, inp: CreateProject, storyboard: Storyboard | None = None) -> dict:
        pid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        p = {
            "id": pid, "created_at": time.time(), "input": inp.model_dump(), "status": "queued", "progress": 0,
            "message": "Waiting in queue", "storyboard": storyboard.model_dump(by_alias=True) if storyboard else None,
            "scenes": [], "video_url": None, "captions_url": None, "duration": None, "error": None, "log": [],
            "title": storyboard.title if storyboard else None,
        }
        self.projects[pid] = p
        self.save(p)
        return p

    def delete(self, pid: str):
        self.projects.pop(pid, None)
        shutil.rmtree(DATA / pid, ignore_errors=True)


store = Store()
queue: asyncio.Queue[str] = asyncio.Queue()


def _probe(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def _update(p: dict, **kw):
    p.update(kw)
    if "message" in kw:
        p["log"].append({"t": time.time(), "m": kw["message"]})
        p["log"] = p["log"][-60:]
    store.save(p)


async def worker():
    while True:
        pid = await queue.get()
        p = store.projects.get(pid)
        if p:
            try:
                await run(p)
            except Exception as e:  # noqa: BLE001
                _update(p, status="error", error=str(e)[:1000], message=f"Failed: {str(e)[:200]}")
        queue.task_done()


async def run(p: dict):
    inp = CreateProject(**p["input"])
    pdir = DATA / p["id"]
    pdir.mkdir(exist_ok=True)

    # 1. script
    if p.get("storyboard"):
        sb = Storyboard.model_validate(p["storyboard"])
        _update(p, status="writing", progress=8, message="Using edited storyboard")
    else:
        _update(p, status="writing", progress=3, message="Writing the script and storyboard…")
        sb = await llm.generate_storyboard(inp.prompt, inp.duration, inp.language, inp.theme, script=inp.script if inp.mode == "script" else None)
        _update(p, storyboard=sb.model_dump(by_alias=True), title=sb.title, progress=12,
                message=f"Storyboard ready: {len(sb.scenes)} scenes")

    # 2. voice
    voice = inp.voice_id or os.environ.get("ELEVENLABS_DEFAULT_VOICE") or await _default_voice()
    _update(p, status="voicing", progress=14, message="Generating the voice-over…")
    sem = asyncio.Semaphore(int(os.environ.get("ELEVENLABS_CONCURRENCY", "2")))
    done = 0

    async def voice_one(i, sc):
        nonlocal done
        async with sem:
            mp3 = pdir / f"voice_{i}.mp3"
            words = await tts.synthesize(sc.narration, voice, str(mp3))
            done += 1
            _update(p, progress=14 + int(22 * done / len(sb.scenes)), message=f"Voice-over {done}/{len(sb.scenes)}")
            return str(mp3), words, _probe(str(mp3))

    async def illustrate(i, sc):
        if inp.visuals != "illustrated" or not sc.illustration or sc.type not in ILLUSTRATED:
            return None  # data-only layouts (bars, stat, flow, compare, diagram) don't place art; skip the cost
        out = await images.generate(sb.theme, sc.illustration, pdir / f"illus_{i}.png")
        if out:
            p["log"].append({"t": time.time(), "m": f"Illustration {i + 1} ready"})
        return f"/data/projects/{p['id']}/illus_{i}.png" if out else None

    if inp.visuals == "illustrated":
        _update(p, message="Generating the voice-over and illustrations…")
    voiced, illus_urls = await asyncio.gather(
        asyncio.gather(*(voice_one(i, sc) for i, sc in enumerate(sb.scenes))),
        asyncio.gather(*(illustrate(i, sc) for i, sc in enumerate(sb.scenes))),
    )

    # 3. compose
    _update(p, status="composing", progress=38, message="Laying out scenes and syncing animation…")
    T = get_theme(sb.theme)
    spec_scenes, offsets, offset = [], [], 0.0
    for i, (sc, (mp3, words, adur)) in enumerate(zip(sb.scenes, voiced)):
        s = compose.compose_scene(sc, T, words, adur, is_last=(i == len(sb.scenes) - 1), hand=inp.hand, image_url=illus_urls[i])
        s.update({"id": i, "audio": mp3, "thumb": str(pdir / f"thumb_{i}.png"), "hand": inp.hand and T.get("hand") != "none", "mono": bool(T.get("mono"))})
        spec_scenes.append(s)
        offsets.append((offset, words))
        offset += s["duration"]
    captions = None
    if inp.captions:
        captions = str(pdir / "captions.srt")
        compose.srt(offsets, captions)
    else:
        compose.srt(offsets, str(pdir / "captions.srt"))
    spec = {"fps": 24, "scale": 1.5 if inp.hd else 1, "concurrency": 3, "lead": compose.LEAD,
            "captions": captions, "theme": player_theme(T), "scenes": spec_scenes}
    (pdir / "spec.json").write_text(json.dumps(spec))
    p["scenes"] = [{"index": i, "type": sc.type, "heading": sc.heading, "narration": sc.narration,
                    "duration": s["duration"], "start": offsets[i][0], "thumb_url": f"/media/{p['id']}/thumb_{i}.png"}
                   for i, (sc, s) in enumerate(zip(sb.scenes, spec_scenes))]
    _update(p, progress=40, message=f"Rendering {int(offset)} s of video…", status="rendering", duration=round(offset, 1))

    # 4. render
    total_frames = sum(round(s["duration"] * spec["fps"]) for s in spec_scenes)
    out = pdir / "video.mp4"
    proc = await asyncio.create_subprocess_exec(
        "node", str(ROOT / "renderer" / "render.mjs"), str(pdir / "spec.json"), str(out),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=str(ROOT))
    frames_done = {}
    last_save = 0.0
    async for raw in proc.stdout:
        try:
            ev = json.loads(raw.decode().strip())
        except Exception:
            continue
        if ev.get("event") == "frame":
            frames_done[ev["scene"]] = ev["frame"]
        elif ev.get("event") == "scene_done":
            frames_done[ev["scene"]] = ev["frames"]
        elif ev.get("event") in ("page", "pageerror"):
            p["log"].append({"t": time.time(), "m": "renderer: " + ev.get("text", "")[:200]})
        done_frames = sum(frames_done.values())
        if time.time() - last_save > 0.8:
            _update(p, progress=40 + int(56 * done_frames / max(1, total_frames)),
                    message=f"Rendering frames {done_frames}/{total_frames}")
            last_save = time.time()
    rc = await proc.wait()
    if rc != 0:
        err = (await proc.stderr.read()).decode()[-1500:]
        raise RuntimeError(f"renderer failed: {err}")
    shutil.rmtree(pdir / ".render", ignore_errors=True)
    _update(p, status="done", progress=100, message="Done", video_url=f"/media/{p['id']}/video.mp4",
            captions_url=f"/media/{p['id']}/captions.srt", duration=round(_probe(str(out)), 1))


_voice_cache: dict = {}


async def _default_voice() -> str:
    if "id" not in _voice_cache:
        voices = await tts.list_voices()
        pref = ["Sarah", "Rachel", "Matilda", "Alice", "Brian", "Daniel"]
        by = {v["name"]: v["voice_id"] for v in voices}
        _voice_cache["id"] = next((by[n] for n in pref if n in by), voices[0]["voice_id"])
    return _voice_cache["id"]
