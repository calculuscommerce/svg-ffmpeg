"""Usage ledger: every billable call is recorded with units, provider cost (USD) and the credits charged to the customer.

Entries are appended to data/ledger.jsonl (durable, one JSON object per line) and mirrored into the project record so
the UI can show a per-video cost breakdown. Rates live in RATES and can be overridden from the environment so a price
change never requires a code change.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "ledger.jsonl"
LEDGER.parent.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


# ---- provider rate card (USD) ---------------------------------------------------------------------------------------
RATES = {
    "openai.gpt-4.1.input_per_1m":   _f("RATE_GPT41_INPUT", 2.00),
    "openai.gpt-4.1.output_per_1m":  _f("RATE_GPT41_OUTPUT", 8.00),
    "openai.gpt-image-1.output_per_1m_tokens": _f("RATE_IMAGE_OUTPUT", 40.00),   # image output tokens
    "openai.gpt-image-1.input_per_1m_tokens":  _f("RATE_IMAGE_INPUT", 5.00),     # text prompt tokens
    "elevenlabs.per_char":           _f("RATE_ELEVEN_PER_CHAR", 0.00018),        # ~Starter/Creator blended; 1 credit = 1 char
    "render.per_video_minute":       _f("RATE_RENDER_PER_MIN", 0.012),           # 4 vCPU box ≈ $0.15/h, ~5 min/min of video
}

# ---- customer credits ------------------------------------------------------------------------------------------------
# 1 credit = one finished minute in a standard theme. Premium-art themes cost a multiplier. Re-renders that re-voice
# charge a fraction; pure re-layout is free.
CREDIT_PER_MINUTE = _f("CREDIT_PER_MINUTE", 1.0)
PREMIUM_MULTIPLIER = _f("CREDIT_PREMIUM_MULTIPLIER", 2.0)
RERENDER_FRACTION = _f("CREDIT_RERENDER_FRACTION", 0.25)
PREMIUM_THEMES = set(os.environ.get("CREDIT_PREMIUM_THEMES", "editorial-monochrome").split(","))


def video_credits(duration_target_s: int, theme: str, *, rerender: bool = False) -> float:
    base = (duration_target_s / 60.0) * CREDIT_PER_MINUTE
    if theme in PREMIUM_THEMES:
        base *= PREMIUM_MULTIPLIER
    if rerender:
        base *= RERENDER_FRACTION
    return round(math.ceil(base * 4) / 4, 2)  # quarter-credit granularity


# ---- pricing helpers -------------------------------------------------------------------------------------------------
def cost_llm(model: str, input_tokens: int, output_tokens: int) -> float:
    return input_tokens / 1e6 * RATES["openai.gpt-4.1.input_per_1m"] + output_tokens / 1e6 * RATES["openai.gpt-4.1.output_per_1m"]


def cost_image(output_tokens: int, input_tokens: int = 0) -> float:
    return output_tokens / 1e6 * RATES["openai.gpt-image-1.output_per_1m_tokens"] + input_tokens / 1e6 * RATES["openai.gpt-image-1.input_per_1m_tokens"]


def cost_tts(chars: int) -> float:
    return chars * RATES["elevenlabs.per_char"]


def cost_render(video_seconds: float) -> float:
    return video_seconds / 60.0 * RATES["render.per_video_minute"]


# ---- recording -------------------------------------------------------------------------------------------------------
def record(project: dict | None, service: str, kind: str, units: float, unit: str, cost_usd: float, **meta) -> dict:
    """service: openai | elevenlabs | render | credits ; kind: storyboard | tts | image | image-cached | frames | charge"""
    entry = {"t": round(time.time(), 3), "project": project["id"] if project else None, "service": service, "kind": kind,
             "units": round(units, 4), "unit": unit, "cost_usd": round(cost_usd, 6), **meta}
    with _lock:
        with LEDGER.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if project is not None:
        project.setdefault("ledger", []).append(entry)
    return entry


def project_summary(project: dict) -> dict:
    by: dict[str, dict] = defaultdict(lambda: {"units": 0.0, "cost_usd": 0.0, "calls": 0, "unit": ""})
    total = 0.0
    credits = 0.0
    for e in project.get("ledger", []):
        if e["service"] == "credits":
            credits += e["units"]
            continue
        key = f'{e["service"]}:{e["kind"]}'
        by[key]["units"] += e["units"]; by[key]["cost_usd"] += e["cost_usd"]; by[key]["calls"] += 1; by[key]["unit"] = e["unit"]
        total += e["cost_usd"]
    return {"cost_usd": round(total, 4), "credits": credits, "lines": {k: {**v, "units": round(v["units"], 2), "cost_usd": round(v["cost_usd"], 4)} for k, v in by.items()}}


def read_all(since: float | None = None, until: float | None = None) -> list[dict]:
    out = []
    if not LEDGER.exists():
        return out
    with LEDGER.open() as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and e["t"] < since:
                continue
            if until and e["t"] > until:
                continue
            out.append(e)
    return out


def usage_report(since: float | None = None, until: float | None = None, projects: dict | None = None) -> dict:
    entries = read_all(since, until)
    by_service: dict[str, dict] = defaultdict(lambda: {"units": 0.0, "cost_usd": 0.0, "calls": 0, "unit": ""})
    by_day: dict[str, dict] = defaultdict(lambda: {"cost_usd": 0.0, "credits": 0.0, "videos": set()})
    by_theme: dict[str, dict] = defaultdict(lambda: {"cost_usd": 0.0, "credits": 0.0, "videos": set()})
    total, credits = 0.0, 0.0
    for e in entries:
        day = time.strftime("%Y-%m-%d", time.localtime(e["t"]))
        theme = (projects or {}).get(e.get("project") or "", {}).get("storyboard", {}) or {}
        theme = theme.get("theme", "unknown") if isinstance(theme, dict) else "unknown"
        if e["service"] == "credits":
            credits += e["units"]; by_day[day]["credits"] += e["units"]; by_theme[theme]["credits"] += e["units"]
            if e.get("project"): by_day[day]["videos"].add(e["project"]); by_theme[theme]["videos"].add(e["project"])
            continue
        key = f'{e["service"]}:{e["kind"]}'
        by_service[key]["units"] += e["units"]; by_service[key]["cost_usd"] += e["cost_usd"]; by_service[key]["calls"] += 1; by_service[key]["unit"] = e["unit"]
        by_day[day]["cost_usd"] += e["cost_usd"]; by_theme[theme]["cost_usd"] += e["cost_usd"]
        total += e["cost_usd"]
    return {
        "since": since, "until": until, "cost_usd": round(total, 4), "credits": round(credits, 2),
        "by_service": {k: {**v, "units": round(v["units"], 2), "cost_usd": round(v["cost_usd"], 4)} for k, v in sorted(by_service.items())},
        "by_day": {d: {"cost_usd": round(v["cost_usd"], 4), "credits": v["credits"], "videos": len(v["videos"])} for d, v in sorted(by_day.items())},
        "by_theme": {t: {"cost_usd": round(v["cost_usd"], 4), "credits": v["credits"], "videos": len(v["videos"])} for t, v in sorted(by_theme.items())},
        "rates": RATES, "credit_rules": {"per_minute": CREDIT_PER_MINUTE, "premium_multiplier": PREMIUM_MULTIPLIER,
                                         "premium_themes": sorted(PREMIUM_THEMES), "rerender_fraction": RERENDER_FRACTION},
    }
