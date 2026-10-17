"""Theme gallery thumbnails: the demo scene rendered once per theme, cached under data/themes/."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from . import compose, images
from .themes import GALLERY, THEMES, demo_for, player_theme

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "themes"
_lock = asyncio.Lock()


def thumb_path(name: str) -> Path:
    return OUT / f"{name}.png"


async def ensure_thumbs(force: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [n for n in GALLERY if force or not thumb_path(n).exists()]
    if not missing:
        return
    async with _lock:
        missing = [n for n in GALLERY if force or not thumb_path(n).exists()]
        if not missing:
            return
        scenes = []
        arts = await asyncio.gather(*(images.generate(n, demo_for(n).illustration, OUT / f"{n}-art.png") if not THEMES[n].get("no_images") and demo_for(n).illustration else asyncio.sleep(0) for n in missing))
        for n, art in zip(missing, arts):
            T = THEMES[n]
            sc = demo_for(n)
            words = [(w, i * 0.3, i * 0.3 + 0.25) for i, w in enumerate(sc.narration.split())]
            s = compose.compose_scene(sc, T, words, len(words) * 0.3, image_url=f"/data/themes/{n}-art.png" if art else None)
            s.update({"id": len(scenes), "thumb": str(thumb_path(n)), "theme": player_theme(T), "stillAt": s["duration"] - 0.2})
            scenes.append(s)
        spec = OUT / "spec.json"
        spec.write_text(json.dumps({"fps": 24, "scale": 0.5, "stills": True, "scenes": scenes}))
        proc = await asyncio.create_subprocess_exec("node", str(ROOT / "renderer" / "render.mjs"), str(spec), str(OUT / "x.mp4"),
                                                    cwd=str(ROOT), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(err.decode()[-500:])
