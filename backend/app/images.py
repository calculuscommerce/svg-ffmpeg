"""Per-scene illustrations from gpt-image-1, cached by (style, brief)."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from openai import AsyncOpenAI

from .themes import DEFAULT_IMAGE_OPTS, IMAGE_OPTS, STYLES

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "images"
CACHE.mkdir(parents=True, exist_ok=True)

NEG_TRANSPARENT = (" Isolated subject on a fully transparent background, nothing behind it. No text, no letters, no numbers, "
                   "no labels, no captions, no watermark, no border, no frame.")
NEG_OPAQUE = (" Plain, even, uncluttered paper background with no scenery behind the subject. No captions, titles or floating "
              "labels{screen}; no watermark, no border, no frame.")


def opts_for(theme_name: str) -> dict:
    return {**DEFAULT_IMAGE_OPTS, **IMAGE_OPTS.get(theme_name, {})}

_sem = asyncio.Semaphore(int(os.environ.get("OPENAI_IMAGE_CONCURRENCY", "4")))


def prompt_for(theme_name: str, brief: str) -> str:
    style = STYLES.get(theme_name, STYLES["hand-drawn"])
    o = opts_for(theme_name)
    if o["background"] == "opaque":
        neg = NEG_OPAQUE.format(screen=" (short realistic text on device screens or signs is fine)" if o["screen_text"] else "; no text anywhere")
        paper = f" The paper colour is exactly {o['paper']}." if o.get("paper") else ""
        return f"{style} Subject: {brief.strip().rstrip('.')}.{neg}{paper}"
    return f"{style} Subject: {brief.strip().rstrip('.')}.{NEG_TRANSPARENT}"


def cache_path(theme_name: str, brief: str) -> Path:
    key = hashlib.sha1(prompt_for(theme_name, brief).encode()).hexdigest()[:16]
    return CACHE / f"{key}.png"


async def generate(theme_name: str, brief: str, dest: Path, *, quality: str | None = None) -> Path | None:
    """Generate (or reuse) the illustration and copy it to dest. Returns None on failure (caller falls back)."""
    cp = cache_path(theme_name, brief)
    if not cp.exists():
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        o = opts_for(theme_name)
        q = quality or o.get("quality") or os.environ.get("OPENAI_IMAGE_QUALITY", "medium")
        last = None
        for attempt in range(3):
            try:
                async with _sem:
                    r = await client.images.generate(model=os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                                                     prompt=prompt_for(theme_name, brief), size="1536x1024",
                                                     quality=q, background=o["background"], output_format="png")
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
    o = opts_for(theme_name)
    if o.get("key_bg") and shutil.which("magick"):
        # the model only approximates a flat colour; snap everything near the corner colour to the exact page colour
        try:
            corner = subprocess.run(["magick", str(dest), "-format", "%[pixel:p{8,8}]", "info:"], capture_output=True, text=True, check=True).stdout.strip()
            subprocess.run(["magick", str(dest), "-fuzz", "14%", "-fill", o["key_bg"], "-opaque", corner, str(dest)], check=True, capture_output=True)
        except Exception as e:  # noqa: BLE001
            print("bg keying skipped:", str(e)[:120])
    return dest
