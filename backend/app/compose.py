"""Storyboard + TTS word timestamps -> render spec for renderer/render.mjs."""
from __future__ import annotations

from .models import Scene
from .templates import render_scene
from .tts import norm

LEAD = 0.5   # silence before narration (must match renderer)
TAIL = 0.9   # pause after narration


def find_cue(cue: str, words: list[tuple[str, float, float]], start: int) -> tuple[float | None, int]:
    toks = [norm(t) for t in cue.split() if norm(t)]
    if not toks or not words:
        return None, start
    W = [norm(w) for w, _, _ in words]
    # exact sequence
    for i in range(start, len(W) - len(toks) + 1):
        if W[i:i + len(toks)] == toks:
            return words[i][1], i
    # first two tokens / first token
    for L in (2, 1):
        if len(toks) >= L:
            for i in range(start, len(W) - L + 1):
                if W[i:i + L] == toks[:L]:
                    return words[i][1], i
    # any token (longest first) after start
    for t in sorted(toks, key=len, reverse=True):
        if len(t) < 4:
            continue
        for i in range(start, len(W)):
            if W[i] == t or (len(t) > 5 and W[i].startswith(t[:5])):
                return words[i][1], i
    return None, start


def schedule(anims: list[dict], words, speech_end: float) -> list[dict]:
    """Assign absolute start times. words times are already offset by LEAD."""
    n = len(anims)
    t = [None] * n
    ptr = 0
    for i, a in enumerate(anims):
        if "t" in a:
            t[i] = float(a["t"])
        elif a.get("cue"):
            tm, idx = find_cue(a["cue"], words, ptr)
            if tm is not None:
                t[i] = tm
                ptr = idx
    # pass 2: anchor anims (no rel) that are still unknown -> spread evenly between known anchors
    is_rel = ["rel" in a and "t" not in a for a in anims]
    anchors = [i for i in range(n) if not is_rel[i]]
    for idx, i in enumerate(anchors):
        if t[i] is not None:
            continue
        prev_known = [a for a in anchors[:idx] if t[a] is not None]
        next_known = [a for a in anchors[idx + 1:] if t[a] is not None]
        j = prev_known[-1] if prev_known else None
        k = next_known[0] if next_known else None
        t0 = t[j] if j is not None else LEAD
        gap_steps = (anchors.index(k) if k is not None else len(anchors)) - (anchors.index(j) if j is not None else -1)
        t1 = t[k] if k is not None else max(speech_end - 0.6, t0 + 0.9 * gap_steps)
        pos = idx - (anchors.index(j) if j is not None else -1)
        t[i] = t0 + (t1 - t0) * pos / gap_steps
    # pass 3: rel anims follow the anim immediately before them (which is now always resolved)
    for i, a in enumerate(anims):
        if t[i] is None:
            t[i] = (t[i - 1] if i > 0 else LEAD) + float(a.get("rel", 0.3))
    # enforce order for anims that followed an earlier one (never earlier than previous - 0.05) and min gap
    for i in range(1, n):
        if "t" in anims[i]:
            continue
        if t[i] < t[i - 1]:
            t[i] = t[i - 1] + (0.0 if "rel" in anims[i] else 0.2)
    out = []
    for a, tt in zip(anims, t):
        b = {k: v for k, v in a.items() if k not in ("cue", "rel")}
        b["t"] = round(max(0.05, tt), 3)
        out.append(b)
    return out


HAND_FX = {"draw", "wipe", "scalex", "pop", "grow", "slide", "fade"}


def serialize_for_hand(anims: list[dict]) -> list[dict]:
    """One pen, one action at a time: push each hand-drawn anim to start after the previous one ends."""
    order = sorted(range(len(anims)), key=lambda i: anims[i]["t"])
    prev_end = 0.0
    for i in order:
        a = anims[i]
        if a["fx"] not in HAND_FX:
            continue
        if a["fx"] in ("pop", "grow", "slide", "fade"):
            a["dur"] = max(float(a.get("dur", 0.6)), 0.9)   # sketching an element takes longer than a pop
        a["t"] = round(max(a["t"], prev_end + 0.08), 3)
        prev_end = a["t"] + float(a.get("dur", 0.6))
    return anims


def compose_scene(scene: Scene, theme: dict, words, audio_dur: float, *, is_last=False, hand=False) -> dict:
    svg, anims = render_scene(scene, theme)
    words = [(w, s + LEAD, e + LEAD) for w, s, e in words]
    speech_end = LEAD + audio_dur
    timed = schedule(anims, words, speech_end)
    if hand:
        timed = serialize_for_hand(timed)
        # serialising can push the pen past the narration: compress the whole schedule back towards it
        hand_anims = [a for a in timed if a["fx"] in HAND_FX]
        if hand_anims:
            first = min(a["t"] for a in hand_anims)
            last_end = max(a["t"] + float(a.get("dur", 0.6)) for a in hand_anims)
            target_end = speech_end + 0.4
            if last_end > target_end and last_end > first:
                k = max(0.5, (target_end - first) / (last_end - first))
                for a in timed:
                    if a["fx"] in ("bob", "spin", "pulse", "flow"):
                        continue
                    a["t"] = round(first + (a["t"] - first) * k, 3) if a["t"] >= first else a["t"]
                    a["dur"] = round(float(a.get("dur", 0.6)) * k, 3)
    anim_end = max([a["t"] + float(a.get("dur", 0.6)) for a in timed if a["fx"] not in ("bob", "spin", "pulse", "flow")] + [0])
    duration = max(speech_end + (TAIL + 0.6 if is_last else TAIL), anim_end + 0.7, 2.5)
    return {"svgText": svg, "anim": timed, "camera": "drift", "duration": round(duration, 3)}


def srt(scenes_words: list[tuple[float, list[tuple[str, float, float]]]], path: str, max_words=8):
    """scenes_words = [(scene_offset_seconds, words)] -> write SRT."""
    idx = 1
    out = []

    def ts(x):
        h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"

    for off, words in scenes_words:
        chunk = []
        for w in words:
            chunk.append(w)
            if len(chunk) >= max_words or w[0].endswith((".", "?", "!", ",")) and len(chunk) >= 4:
                out.append((idx, off + LEAD + chunk[0][1], off + LEAD + chunk[-1][2] + 0.15, " ".join(c[0] for c in chunk)))
                idx += 1; chunk = []
        if chunk:
            out.append((idx, off + LEAD + chunk[0][1], off + LEAD + chunk[-1][2] + 0.15, " ".join(c[0] for c in chunk)))
            idx += 1
    with open(path, "w") as f:
        for i, a, b, txt in out:
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n\n")
