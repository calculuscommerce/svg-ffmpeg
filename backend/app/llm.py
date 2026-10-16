"""Topic/content -> Storyboard via OpenAI, constrained to the scene templates and asset library."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import ValidationError

from .models import Storyboard
from .themes import THEMES

ROOT = Path(__file__).resolve().parents[2]


def asset_names() -> list[str]:
    txt = (ROOT / "lib" / "parts.svg").read_text()
    names = re.findall(r'<g id="([a-z0-9-]+)"', txt)
    skip = {"icons", "soil-body", "roots", "stem", "sun-rays", "leaf-shape"}
    return [n for n in names if n not in skip and not n.startswith("hand-")]


# words/sec for ElevenLabs at normal pace, plus ~1.3 s of lead/tail per scene
BUDGET = {
    30: dict(scenes="3 to 4", words="55 to 65", per_scene="12 to 20", max_words=72, max_scenes=4),
    60: dict(scenes="6 to 7", words="120 to 135", per_scene="14 to 26", max_words=148, max_scenes=7),
    300: dict(scenes="18 to 22", words="650 to 720", per_scene="22 to 45", max_words=760, max_scenes=23),
}

SYSTEM = """You are a senior explainer-video director and scriptwriter. You turn a topic or source content into a storyboard for a hand-drawn whiteboard-style animated video (think "Photosynthesis explained" / Kurzgesagt-lite on a whiteboard). Output STRICT JSON only.

## Output schema
{
  "title": string,                       // 2-6 words
  "theme": one of %(themes)s,            // pick what suits the topic
  "scenes": [ Scene, ... ]
}
Scene = {
  "type": one of ["title","concept","cards","bars","steps","list","stat","flow","compare","callout","diagram","outro"],
  "narration": string,                   // spoken voice-over for this scene; natural, conversational, concrete
  "heading": string|null,                // on-screen heading, <= 7 words
  "subheading": string|null,             // <= 10 words, optional
  "items": [ {"icon": string|null, "label": string|null, "value": string|null, "caption": string|null, "cue": string|null} ],
  "connections": [ {"from": int, "to": int, "label": string|null, "cue": string|null} ],   // flow scenes only
  "svg": string|null                     // diagram scenes only
}

## Scene types and how `items` are used
- title: first scene. heading = title, subheading = hook question. items[0].icon = hero icon (optional). Narration = hook.
- concept: one hero illustration with labelled callouts. items[0] = hero {icon, label}. items[1..4] = callouts {label (<=4 words), caption (<=8 words), cue}.
- cards: 2-4 cards. each item = {icon, label (<=3 words), value (short figure like "₹1,00,000", "12%%", "3x" or null), caption (<=7 words), cue}.
- bars: 2-5 horizontal bars for comparing quantities. each item = {label, value (a number with optional unit/prefix e.g. "₹6,619", "42%%", "1.5 km"), caption?, cue}. Values must be numeric so bars can be drawn to scale.
- steps: 3-5 sequential steps. each item = {icon, label (<=3 words), caption (<=8 words), cue}.
- list: 3-5 bullet points with check marks. each item = {label (<=8 words), icon?, cue}.
- stat: 1-3 big numbers. each item = {value (e.g. "70%%", "₹8,885", "2.5 billion"), label (<=6 words), icon?, cue}.
- flow: 3-6 nodes with arrows. items = nodes {icon, label (<=3 words), cue}; connections = arrows {from, to, label (<=3 words), cue}. Node indexes are 0-based.
- compare: exactly 2 items, A vs B. each item = {icon, label (<=3 words), caption = 2-3 short points separated by ";", cue}.
- callout: a highlighted box for a warning, tip or key takeaway. items[0] = {icon, label (<=8 words), caption (<=12 words)}. heading optional.
- diagram: ONLY for a mechanism that no other type can show (a circuit, a cycle with arrows, anatomy, geometry, a before/after). Use at most one per video. Provide `svg`: an SVG fragment (no <svg> root) drawn in a 1100 x 480 coordinate box, origin top-left — USE THE WHOLE BOX: spread parts out, at least 80 px apart, big shapes (circles r>=40, boxes >=160x80). Rules: simple shapes (path, circle, rect, line, text), stroke "#2b2b2b" width 4, fills from the palette {%(palette)s}, labels in <text font-size="30"> placed OUTSIDE/below shapes (never on top of other elements), arrows as paths with a small triangle head, no external refs, no <style>, no transform on elements you want animated. Wrap each logical part in <g data-cue="phrase from narration"> so it draws on when spoken (3-6 groups). Prefer library parts for objects: <g transform="translate(x,y)"><g data-include="name" data-fit="W H"/></g>. Also fill items[] with the same labels for accessibility.
- outro: last scene. heading = one-line takeaway (<=8 words). items = 2-3 {label (<=6 words), icon} recap points. Narration = conclusion.

## Asset library (use these exact names for `icon`)
%(assets)s
If no icon fits, use the closest one or null — never invent a name.

## Cues (timing sync)
`cue` is a short exact phrase (2-5 words) copied VERBATIM from that scene's narration, at the moment the element should appear. Each item should have a cue. Cues must appear in order in the narration.

## Writing rules
- Target total length: %(words)s spoken words across %(scenes)s scenes, %(per_scene)s words per scene. Hit the word budget — it determines video length.
- One idea per scene. Vary scene types; never use the same type twice in a row (except cards/steps once if needed). Always start with "title" and end with "outro".
- On-screen text is short (labels <= 4 words). Narration carries the explanation; the screen shows the structure.
- Be concrete: use real numbers, examples, analogies. Get facts right. If the user supplies content, stay faithful to it and do not add claims it does not support.
- Numbers: if the user's content uses a currency, keep it. Format Indian rupees as ₹1,00,000 (lakh grouping). Write numbers in narration as words when they are spoken ("one lakh rupees").
- Language: write narration and on-screen text in %(language)s.
- Audience: general global audience unless the content says otherwise. Explain jargon the first time.
- Return ONLY the JSON object. No markdown fences.
"""


def _system(duration: int, language: str) -> str:
    b = BUDGET[duration]
    return SYSTEM % dict(
        themes=json.dumps(list(THEMES.keys())),
        palette=", ".join(f'"{v}"' for v in ["#1f4aa8", "#5aa9e6", "#e08a1e", "#2e8b57", "#d64545", "#f6c445", "#cfd8e3", "#ffffff"]),
        assets=", ".join(asset_names()),
        words=b["words"], scenes=b["scenes"], per_scene=b["per_scene"], language=language,
    )


SCRIPT_MODE = """

## OWN-SCRIPT MODE (overrides the writing rules above)
The user has written the narration themselves. You are the director, not the writer:
- Split their script into scenes at natural breaks. Each scene's `narration` must be a VERBATIM, contiguous slice of the
  user's script — do not add, remove, reorder or rephrase a single word. Concatenating all scene narrations must
  reproduce the script exactly (whitespace aside). Ignore the word budget; the script's length decides the video length.
- Choose the scene type, heading, items, icons and cues for each slice so the visuals illustrate what is being said.
- Follow any visual instructions the user gives (style, audience, what to show).
"""


async def generate_storyboard(prompt: str, duration: int, language: str = "English", theme: str = "auto",
                              script: str | None = None) -> Storyboard:
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1")
    system = _system(duration, language)
    if script:
        system += SCRIPT_MODE
        user = "Create the storyboard for this script.\n\n"
        if prompt.strip():
            user += f"Visual instructions from the user:\n\"\"\"\n{prompt.strip()}\n\"\"\"\n\n"
        user += f"SCRIPT (narrate exactly as written):\n\"\"\"\n{script.strip()}\n\"\"\""
    else:
        user = f"Create the storyboard for a {duration}-second video.\n\n"
        user += f"Topic / source content from the user:\n\"\"\"\n{prompt.strip()}\n\"\"\""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_err = None
    for attempt in range(3):
        resp = await client.chat.completions.create(
            model=model, messages=messages, temperature=0.7, response_format={"type": "json_object"},
        )
        txt = resp.choices[0].message.content or ""
        try:
            data = json.loads(txt)
            sb = Storyboard.model_validate(data)
            problems = _lint(sb, duration, script)
            hard = [p for p in problems if not p.startswith("soft:")]
            # soft problems (word budget) get one trim request, then we accept the storyboard
            if not hard and (not problems or attempt >= 1):
                if theme and theme != "auto":
                    sb.theme = theme
                return sb
            last_err = "; ".join(p.removeprefix("soft:") for p in problems)
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = str(e)[:800]
        messages.append({"role": "assistant", "content": txt})
        messages.append({"role": "user", "content": f"That JSON had problems: {last_err}. Return the corrected full JSON object only."})
    raise RuntimeError(f"storyboard generation failed: {last_err}")


def _norm_words(t: str) -> list[str]:
    return re.sub(r"[^\w\s]", "", t.lower()).split()


def _lint(sb: Storyboard, duration: int, script: str | None = None) -> list[str]:
    p = []
    b = BUDGET[duration]
    total = sum(len(s.narration.split()) for s in sb.scenes)
    if script:
        want, got = _norm_words(script), _norm_words(" ".join(s.narration for s in sb.scenes))
        if want != got:
            p.append("the scene narrations do not reproduce the user's script verbatim; every word must be kept, "
                     "in order, with nothing added — only split it into scenes")
    elif total > b["max_words"] * 1.08:
        p.append(f"soft:narration is {total} words in total; the limit for a {duration}s video is {b['max_words']}. "
                 f"Cut it to {b['words']} words by tightening every scene (keep the same scenes and facts)")
    if len(sb.scenes) > b["max_scenes"]:
        p.append(f"soft:too many scenes ({len(sb.scenes)}); use at most {b['max_scenes']}")
    if len(sb.scenes) < 2:
        p.append("need at least 2 scenes")
    if sb.scenes and sb.scenes[0].type != "title":
        p.append("first scene must be type 'title'")
    if sb.scenes and sb.scenes[-1].type != "outro":
        p.append("last scene must be type 'outro'")
    names = set(asset_names())
    for i, s in enumerate(sb.scenes):
        if not s.narration.strip():
            p.append(f"scene {i}: empty narration")
        if s.type == "diagram" and not s.svg:
            p.append(f"scene {i}: diagram without svg")
        if s.type == "compare" and len(s.items) != 2:
            p.append(f"scene {i}: compare needs exactly 2 items")
        if s.type in ("cards", "bars", "steps", "list", "flow", "stat", "compare") and len(s.items) < 2:
            p.append(f"scene {i}: {s.type} needs at least 2 items")
        for it in s.items:
            if it.icon and it.icon not in names:
                it.icon = _closest(it.icon, names)
        for c in s.connections:
            if not (0 <= c.source < len(s.items) and 0 <= c.to < len(s.items)):
                p.append(f"scene {i}: connection index out of range")
    return p


def _closest(name: str, names: set[str]) -> str | None:
    n = name.lower().replace("_", "-")
    for cand in names:
        if cand in n or n in cand:
            return cand
    return None
