"""Per-scene illustrations from gpt-image-1, cached by (style, brief)."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import shutil
from pathlib import Path

from openai import AsyncOpenAI

from .themes import STYLES

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "images"
CACHE.mkdir(parents=True, exist_ok=True)

NEGATIVE = (" Isolated subject on a fully transparent background, nothing behind it. No text, no letters, no numbers, "
            "no labels, no captions, no watermark, no border, no frame.")

_sem = asyncio.Semaphore(int(os.environ.get("OPENAI_IMAGE_CONCURRENCY", "4")))


def prompt_for(theme_name: str, brief: str) -> str:
    style = STYLES.get(theme_name, STYLES["hand-drawn"])
    return f"{style} Subject: {brief.strip().rstrip('.')}.{NEGATIVE}"


def cache_path(theme_name: str, brief: str) -> Path:
    key = hashlib.sha1(prompt_for(theme_name, brief).encode()).hexdigest()[:16]
    return CACHE / f"{key}.png"


async def generate(theme_name: str, brief: str, dest: Path, *, quality: str | None = None) -> Path | None:
    """Generate (or reuse) the illustration and copy it to dest. Returns None on failure (caller falls back)."""
    cp = cache_path(theme_name, brief)
    if not cp.exists():
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        q = quality or os.environ.get("OPENAI_IMAGE_QUALITY", "medium")
        last = None
        for attempt in range(3):
            try:
                async with _sem:
                    r = await client.images.generate(model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                                                     prompt=prompt_for(theme_name, brief), size="1536x1024",
                                                     quality=q, background="transparent", output_format="png")
                cp.write_bytes(base64.b64decode(r.data[0].b64_json))
                break
            except Exception as e:  # noqa: BLE001
                last = e
                await asyncio.sleep(2 * (attempt + 1))
        else:
            print("image generation failed:", str(last)[:200])
            return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cp, dest)
    return dest
