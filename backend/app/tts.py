"""ElevenLabs text-to-speech with word-level timestamps."""
from __future__ import annotations

import asyncio
import base64
import os
import re

import httpx

API = "https://api.elevenlabs.io/v1"


def _headers():
    return {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}


async def list_voices() -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{API}/voices", headers=_headers())
        r.raise_for_status()
    out = []
    for v in r.json().get("voices", []):
        labels = v.get("labels") or {}
        out.append({
            "voice_id": v["voice_id"],
            "name": v["name"],
            "accent": labels.get("accent"),
            "gender": labels.get("gender"),
            "description": labels.get("description") or labels.get("descriptive"),
            "use_case": labels.get("use_case") or labels.get("use case"),
            "preview_url": v.get("preview_url"),
        })
    return out


async def synthesize(text: str, voice_id: str, out_path: str) -> list[tuple[str, float, float]]:
    """Write MP3 to out_path and return [(word, start, end), ...] in seconds."""
    body = {
        "text": text,
        "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2, "use_speaker_boost": True},
    }
    async with httpx.AsyncClient(timeout=120) as c:
        for attempt in range(6):
            r = await c.post(f"{API}/text-to-speech/{voice_id}/with-timestamps",
                             params={"output_format": "mp3_44100_128"}, headers=_headers(), json=body)
            if r.status_code == 429 or r.status_code >= 500:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:300]}")
            break
        else:
            raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:300]}")
        data = r.json()
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment")
    return _words(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"])


def _words(chars, starts, ends):
    words, cur, s0, e0 = [], "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append((cur, s0, e0)); cur, s0 = "", None
            continue
        if not cur:
            s0 = s
        cur += ch
        e0 = e
    if cur:
        words.append((cur, s0, e0))
    return words


def norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())
