"""Scene templates: Scene (from the LLM) -> (SVG fragment, ordered animation list).

Each anim is {"sel": css, "fx": name, ...} plus ONE timing hint:
  "cue": phrase       appear when this phrase is spoken (resolved against TTS word timestamps)
  "rel": seconds      offset from the previous anim's start
  "t":   seconds      absolute
  (none)              spread evenly between neighbouring known times
Canvas is 1280x720; content area y 190..690.
"""
from __future__ import annotations

import math
import re
from xml.sax.saxutils import escape

from .models import Item, Scene

W, H = 1280, 720
CHAR_W = 0.46  # average glyph width of Patrick Hand in em (default; see FONT_W for other fonts)
# relative glyph width per font family and the text-size multiplier a theme using it needs
FONT_W = {"hand": 0.46, "caveat": 0.40, "marker": 0.58, "serif": 0.56, "pixel": 1.0, "architect": 0.55, "kalam": 0.52, "oswald": 0.42}
FONT_SIZE = {"hand": 1.0, "caveat": 1.1, "marker": 0.85, "serif": 0.85, "pixel": 0.5, "architect": 0.9, "kalam": 0.95, "oswald": 0.95}
_cur = {"w": CHAR_W, "k": 1.0}


def set_font_metrics(T: dict):
    f = T.get("font_body", "hand")
    _cur["w"] = FONT_W.get(f, CHAR_W)
    _cur["k"] = FONT_SIZE.get(f, 1.0)


def esc(s: str | None) -> str:
    return escape(s or "")


def wrap(text: str | None, size: float, maxw: float, max_lines: int = 3) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    max_chars = max(6, int(maxw / (size * _cur["k"] * _cur["w"])))
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;") + "…"
    return lines


def text(x, y, s, size, fill, *, id=None, anchor="start", maxw=None, bold=False, cls=None, extra="") -> str:
    size = round(size * _cur["k"], 1)
    a = [f'x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"']
    if id: a.append(f'id="{id}"')
    if maxw: a.append(f'data-maxw="{maxw}"')
    if bold: a.append(f'stroke="{fill}" stroke-width="1.4"')
    classes = " ".join(c for c in [cls, "h" if bold else None] if c)
    if classes: a.append(f'class="{classes}"')
    return f'<text {" ".join(a)} {extra}>{esc(s)}</text>'


def multiline(x, y, lines, size, fill, *, id=None, anchor="start", lh=1.25, bold=False) -> str:
    if not lines:
        return ""
    size = round(size * _cur["k"], 1)
    a = [f'x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"']
    if id: a.append(f'id="{id}"')
    if bold: a.append(f'stroke="{fill}" stroke-width="1.2" class="h"')
    spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else size * lh}">{esc(l)}</tspan>' for i, l in enumerate(lines))
    return f'<text {" ".join(a)}>{spans}</text>'


def icon(x, y, name, size, color, *, id=None, anchor="center") -> str:
    if not name:
        return ""
    idattr = f'id="{id}"' if id else ""
    return (f'<g transform="translate({x},{y})"><g {idattr} data-include="{esc(name)}" data-fit="{size} {size}" '
            f'data-anchor="{anchor}" style="color:{color}"/></g>')


def arrow(x1, y1, x2, y2, color, *, id=None, width=6, curve=0.0, dashed=False) -> str:
    """Straight or gently curved arrow with a head. curve = perpendicular bulge in px."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    cx, cy = (x1 + x2) / 2 + nx * curve, (y1 + y2) / 2 + ny * curve
    # head direction = tangent at end
    tx, ty = x2 - cx, y2 - cy
    ang = math.degrees(math.atan2(ty, tx))
    dash = ' stroke-dasharray="14 12"' if dashed else ""
    idattr = f'id="{id}"' if id else ""
    return (f'<g {idattr} fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}"{dash}/>'
            f'<path d="M-18,-12 L0,0 L-18,12" transform="translate({x2:.1f},{y2:.1f}) rotate({ang:.1f})"/></g>')


NUM_RE = re.compile(r"^\s*([^\d\-]*?)\s*(-?\d[\d,]*(?:\.\d+)?)\s*(.*?)\s*$")


def parse_number(value: str | None) -> dict | None:
    """'₹1,00,000' -> count-anim params. None if not numeric."""
    if not value:
        return None
    m = NUM_RE.match(value)
    if not m:
        return None
    prefix, num, suffix = m.groups()
    if suffix and value[m.end(2):m.start(3)].strip() == "" and m.end(2) < m.start(3):
        suffix = " " + suffix
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    if re.search(r"\d,\d\d,\d\d\d", num):
        grouping = "indian"
    elif "," in num:
        grouping = "intl"
    else:
        grouping = "none" if len(num) <= 4 else "intl"
    decimals = len(num.split(".")[1]) if "." in num else 0
    return {"from": 0, "to": v, "prefix": prefix, "suffix": suffix, "grouping": grouping, "decimals": decimals}


def hd_text(s: str | None, T: dict) -> str:
    return (s or "").upper() if T.get("uppercase") else (s or "")


def highlight_box(x, y, s, size, T, *, anchor="start", id="hl") -> str:
    """Marker-highlighter rectangle behind a heading (bold-marker / retro-mint themes)."""
    w = len(s) * size * _cur["k"] * _cur["w"] * (0.92 if T.get("uppercase") else 1.0) + 28
    x0 = x - 14 if anchor == "start" else x - w / 2
    return f'<rect id="{id}" x="{x0:.0f}" y="{y - size * 0.82:.0f}" width="{w:.0f}" height="{size * 1.05:.0f}" rx="8" fill="{T["accent"]}" opacity=".45"/>'


def L(T: dict) -> dict:
    return T.get("layout") or {}


def heading(scene: Scene, T: dict, *, y=100, size=64) -> tuple[list[str], list[dict]]:
    parts, anims = [], []
    style = L(T).get("heading", "left")
    if not scene.heading:
        return parts, anims
    h = hd_text(scene.heading, T)
    dur = min(1.6, 0.35 + 0.045 * len(scene.heading))
    if style == "centered-rule":
        lines = wrap(h, size, 1000, 2)
        sz = size if len(lines) == 1 else round(size * 0.8)
        parts.append(f'<path id="hdr1" d="M240,52 H1040" stroke="{T["muted"]}" stroke-width="1.5"/>')
        parts.append(multiline(640, y + 2 - (0 if len(lines) == 1 else 30), lines, sz, T["primary"], id="hd", anchor="middle", lh=1.1, bold=True))
        parts.append(f'<path id="hdr2" d="M240,{y + 32} H1040" stroke="{T["muted"]}" stroke-width="1.5"/>')
        anims += [{"sel": "#hdr1", "fx": "wipe", "dur": 0.6, "t": 0.2}, {"sel": "#hd", "fx": "wipe", "dur": dur, "rel": 0.2},
                  {"sel": "#hdr2", "fx": "wipe", "dur": 0.6, "rel": 0.4}]
        if scene.subheading:
            parts.append(text(640, y + 72, scene.subheading, 32, T["muted"], id="sub", anchor="middle", maxw=1000, cls="script" if T.get("font_body") == "serif" else None))
            anims.append({"sel": "#sub", "fx": "wipe", "dur": 1.0, "rel": 0.5})
        return parts, anims
    if style == "banner":
        w = len(h) * size * _cur["k"] * _cur["w"] + 60
        parts.append(f'<rect id="hdbox" x="40" y="{y - size * 0.85:.0f}" width="{w:.0f}" height="{size * 1.15:.0f}" fill="{T["primary"]}"/>')
        parts.append(text(70, y, h, size, T["bg"], id="hd", maxw=1120, bold=True))
        anims += [{"sel": "#hdbox", "fx": "wipe", "dur": 0.5, "t": 0.2}, {"sel": "#hd", "fx": "wipe", "dur": dur, "rel": 0.1}]
    elif style == "label":
        parts.append(highlight_box(60, y, h, size, T, id="hdbox"))
        parts.append(text(60, y, h, size, T["primary"], id="hd", maxw=1160, bold=True))
        anims += [{"sel": "#hdbox", "fx": "wipe", "dur": 0.5, "t": 0.2}, {"sel": "#hd", "fx": "wipe", "dur": dur, "rel": 0.1}]
    elif style == "rule-double":
        parts.append(text(60, y, h, size, T["primary"], id="hd", maxw=1160, bold=True))
        parts.append(f'<g id="hdr1" fill="none" stroke="{T["primary"]}"><path d="M60,{y + 22} H1220" stroke-width="2"/><path d="M60,{y + 30} H1220" stroke-width="1"/></g>')
        anims += [{"sel": "#hd", "fx": "wipe", "dur": dur, "t": 0.3}, {"sel": "#hdr1", "fx": "wipe", "dur": 0.8, "rel": 0.3}]
    elif style == "ink":
        # handwritten script heading sitting on the first ruled line, double red-pen underline
        lines = wrap(h, size + 10, 1080, 2)
        sz = size + 10 if len(lines) == 1 else round(size * 0.85)
        parts.append(multiline(130, 96 - (0 if len(lines) == 1 else 30), lines, sz, T["primary"], id="hd", lh=1.05, bold=True))
        tw = min(1080, max(len(l) for l in lines) * sz * 1.1 * 0.40)
        parts.append(f'<g id="hdul" fill="none" stroke="{T["secondary"]}" stroke-width="3" stroke-linecap="round">'
                     f'<path d="M130,112 C{130 + tw * 0.4:.0f},108 {130 + tw * 0.7:.0f},116 {130 + tw:.0f},111"/>'
                     f'<path d="M136,120 C{130 + tw * 0.3:.0f},124 {130 + tw * 0.6:.0f},116 {130 + tw * 0.9:.0f},120"/></g>')
        anims += [{"sel": "#hd", "fx": "wipe", "dur": dur, "t": 0.3}, {"sel": "#hdul", "fx": "draw", "dur": 0.6, "rel": 0.2}]
        if scene.subheading:
            parts.append(text(132, 158, scene.subheading, 32, T["muted"], id="sub", maxw=1080))
            anims.append({"sel": "#sub", "fx": "wipe", "dur": 1.0, "rel": 0.5})
        return parts, anims
    elif style in ("underline", "chalk"):
        lines = wrap(h, size, 1160, 2)
        sz = size if len(lines) == 1 else round(size * 0.8)
        parts.append(multiline(60, y - (0 if len(lines) == 1 else 28), lines, sz, T["primary"], id="hd", lh=1.1, bold=True))
        tw = min(1160, max(len(l) for l in lines) * sz * _cur["k"] * _cur["w"])
        uy = y + 18 + (0 if len(lines) == 1 else sz * 0.9)
        col = T["accent"] if style == "underline" else T["secondary"]
        parts.append(f'<path id="hdul" d="M60,{uy:.0f} C{60 + tw * 0.3:.0f},{uy - 7:.0f} {60 + tw * 0.7:.0f},{uy + 9:.0f} {60 + tw:.0f},{uy - 1:.0f}" fill="none" stroke="{col}" stroke-width="{6 if style == "underline" else 4}" stroke-linecap="round"/>')
        anims += [{"sel": "#hd", "fx": "wipe", "dur": dur, "t": 0.3}, {"sel": "#hdul", "fx": "draw", "dur": 0.5, "rel": 0.2}]
    else:
        lines = wrap(h, size, 1160, 2)
        if len(lines) > 1:
            parts.append(multiline(60, y - 28, lines, round(size * 0.8), T["primary"], id="hd", lh=1.1, bold=True))
        else:
            parts.append(text(60, y, h, size, T["primary"], id="hd", maxw=1160, bold=True))
        anims.append({"sel": "#hd", "fx": "wipe", "dur": dur, "t": 0.3})
    if scene.subheading:
        parts.append(text(62, y + 54, scene.subheading, 36, T["muted"], id="sub", maxw=1160))
        anims.append({"sel": "#sub", "fx": "wipe", "dur": 1.0, "rel": 0.7})
    return parts, anims


def decor(T: dict, idx: int) -> tuple[list[str], list[dict]]:
    """Scene-level decorations that give a theme its personality. Placed in corners, never over content."""
    kind = L(T).get("decor", "none")
    p, a = [], []
    if kind == "doodles":
        c1, c2 = T["accent"], T["secondary"]
        p.append(f'<g id="dd" fill="none" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
                 f'<path d="M1180,60 l6,14 15,2 -11,10 3,15 -13,-7 -13,7 3,-15 -11,-10 15,-2 Z" stroke="{c1}" fill="{c1}"/>'
                 f'<path d="M80,660 c20,-18 30,18 50,0 s30,18 50,0" stroke="{c2}"/>'
                 f'<path d="M1150,650 l5,10 11,2 -8,8 2,11 -10,-5 -10,5 2,-11 -8,-8 11,-2 Z" stroke="{c2}"/>'
                 f'<circle cx="1230" cy="130" r="5" fill="{c2}" stroke="none"/><circle cx="46" cy="60" r="4" fill="{c1}" stroke="none"/></g>')
        a.append({"sel": "#dd", "fx": "draw", "dur": 1.2, "t": 0.6})
    elif kind == "editorial":
        p.append(f'<g id="dd"><rect x="1096" y="36" width="124" height="34" rx="2" fill="none" stroke="{T["muted"]}" stroke-width="1.2"/>'
                 f'{text(1158, 60, f"No. {idx + 1:02d}", 20, T["muted"], anchor="middle")}'
                 f'<path d="M60,690 H1220" stroke="{T["muted"]}" stroke-width="1"/>'
                 f'{text(1220, 712, f"— {idx + 1} —", 18, T["muted"], anchor="end")}</g>')
        a.append({"sel": "#dd", "fx": "fade", "dur": 0.8, "t": 0.4})
    elif kind == "pixels":
        sq = "".join(f'<rect x="{x}" y="{y}" width="14" height="14" fill="{c}"/>' for x, y, c in
                     [(1180, 40, T["primary"]), (1198, 40, T["accent"]), (1216, 40, T["secondary"]), (40, 660, T["secondary"]), (58, 660, T["accent"]), (40, 678, T["primary"])])
        p.append(f'<g id="dd">{sq}</g>')
        a.append({"sel": "#dd", "fx": "fade", "dur": 0.4, "t": 0.5})
    elif kind == "corners":
        m = T["primary"]
        p.append(f'<g id="dd" fill="none" stroke="{m}" stroke-width="2"><path d="M40,80 V40 H80 M1200,40 H1240 V80 M40,640 V680 H80 M1240,640 V680 H1200"/>'
                 f'<path d="M200,700 H1080" stroke-dasharray="6 6" stroke-width="1"/>{text(640, 694, f"FIG. {idx + 1}", 16, m, anchor="middle")}</g>')
        a.append({"sel": "#dd", "fx": "draw", "dur": 1.0, "t": 0.3})
    elif kind == "sticky":
        p.append(f'<g transform="translate(1160,62) rotate(5)"><g id="dd">'
                 f'<rect x="-50" y="-34" width="100" height="68" fill="#000" opacity=".12" transform="translate(4,6)"/>'
                 f'<path d="M-50,-34 H50 V20 L36,34 H-50 Z" fill="{T["accent"]}"/>'
                 f'<path d="M50,20 L36,34 L36,20 Z" fill="#e6c94a"/>'
                 f'<rect x="-28" y="-44" width="56" height="16" fill="#fff" opacity=".55" transform="rotate(-4)"/>'
                 f'{text(0, 8, f"p. {idx + 1}", 28, T["ink"], anchor="middle", cls="script")}</g></g>')
        a.append({"sel": "#dd", "fx": "pop", "dur": 0.5, "t": 0.5})
    return p, a


def cue(it: Item | None):
    return it.cue if it and it.cue else None


def palette(T):
    return [T["primary"], T["accent"], T["good"], T["secondary"], T["bad"]]


# ---------------------------------------------------------------- templates

def t_title(s: Scene, T) -> tuple[str, list[dict]]:
    hero = s.items[0].icon if s.items else None
    p, a = [], []
    tw = 720 if hero else 1160
    tx = 70 if hero else W / 2
    anchor = "start" if hero else "middle"
    lines = wrap(hd_text(s.heading, T), 96, tw, 2)
    p.append(multiline(tx, 260 if len(lines) == 1 else 200, lines, 96, T["primary"], id="hd", anchor=anchor, lh=1.1, bold=True))
    a.append({"sel": "#hd", "fx": "wipe", "dur": 1.4, "t": 0.3})
    uy = 300 if len(lines) == 1 else 350
    ux1, ux2 = (70, 70 + min(tw, 46 * len(lines[0]) if lines else 400)) if hero else (W / 2 - 260, W / 2 + 260)
    p.append(f'<path id="ul" d="M{ux1},{uy} C{ux1 + 100},{uy - 8} {ux2 - 120},{uy + 10} {ux2},{uy - 2}" fill="none" stroke="{T["accent"]}" stroke-width="8" stroke-linecap="round"/>')
    a.append({"sel": "#ul", "fx": "draw", "dur": 0.7, "rel": 1.0})
    if s.subheading:
        sl = wrap(s.subheading, 46, tw, 2)
        p.append(multiline(tx, uy + 70, sl, 46, T["ink"], id="sub", anchor=anchor))
        a.append({"sel": "#sub", "fx": "wipe", "dur": 1.2, "rel": 0.5})
    if hero:
        p.append(icon(1000, 400, hero, 420, T["primary"], id="hero"))
        a.append({"sel": "#hero", "fx": "pop", "dur": 0.8, "cue": cue(s.items[0]) or None, "rel": None if cue(s.items[0]) else 0.4})
        a.append({"sel": "#hero", "fx": "bob", "dy": 7, "period": 3.0, "rel": 0.8})
    return "".join(p), _clean(a)


def t_concept(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    hero = s.items[0] if s.items else None
    callouts = s.items[1:5]
    hx, hy = 640, 450
    if hero and hero.icon:
        p.append(icon(hx, hy, hero.icon, 360, T["primary"], id="hero"))
        a.append({"sel": "#hero", "fx": "pop", "dur": 0.8, "rel": 0.5})  # hero shows right after the heading; callouts follow the cues
        if hero.label:
            p.append(text(hx, 665, hero.label, 36, T["muted"], id="hlabel", anchor="middle", maxw=400))
            a.append({"sel": "#hlabel", "fx": "wipe", "dur": 0.8, "rel": 0.5})
    slots = [(70, 260, "L", -70), (70, 560, "L", 70), (900, 260, "R", -70), (900, 560, "R", 70)]
    if len(callouts) <= 2:
        slots = [(70, 290, "L", -60), (900, 290, "R", -60), (70, 560, "L", 70), (900, 560, "R", 70)][: len(callouts)]
    for i, (it, (x, y, side, oy)) in enumerate(zip(callouts, slots)):
        col = palette(T)[i % 5]
        p.append(text(x, y, it.label or "", 42, col, id=f"cl{i}", maxw=320, bold=True))
        cap = wrap(it.caption, 28, 320, 2)
        p.append(multiline(x, y + 40, cap, 28, T["muted"], id=f"cc{i}"))
        if side == "L":
            x1, x2 = x + 330, hx - 150
        else:
            x1, x2 = x - 20, hx + 150
        p.append(f'<path id="ln{i}" d="M{x1},{y - 12} L{x2},{hy + oy}" fill="none" stroke="{col}" stroke-width="3.5" stroke-dasharray="2 10" stroke-linecap="round"/>'
                 f'<circle id="dot{i}" cx="{x2}" cy="{hy + oy}" r="7" fill="{col}"/>')
        a.append({"sel": f"#ln{i}", "fx": "draw", "dur": 0.5, "cue": cue(it)})
        a.append({"sel": f"#dot{i}", "fx": "pop", "dur": 0.4, "rel": 0.3})
        a.append({"sel": f"#cl{i}", "fx": "wipe", "dur": 0.7, "rel": 0.1})
        if cap:
            a.append({"sel": f"#cc{i}", "fx": "wipe", "dur": 0.9, "rel": 0.4})
    return "".join(p), _clean(a)


def t_cards(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    items = s.items[:4] or [Item(label="—")]
    n = len(items)
    gap, x0, y0, h = 30, 60, 200, 470
    w = (1160 - gap * (n - 1)) / n
    for i, it in enumerate(items):
        col = palette(T)[i % 5]
        x = x0 + i * (w + gap)
        cx = x + w / 2
        g = [f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="28" fill="{T["card"]}" stroke="{col}" stroke-width="6"/>']
        isz = min(150, w * 0.5)
        if it.icon:
            g.append(icon(cx, y0 + 125, it.icon, isz, col))
        g.append(text(cx, y0 + 255, it.label or "", 46, T["ink"], anchor="middle", maxw=w - 40, bold=True))
        num = parse_number(it.value)
        if it.value:
            g.append(text(cx, y0 + 335, it.value if not num else "", 60, col, id=f"v{i}", anchor="middle", maxw=w - 40, bold=True))
        cap = wrap(it.caption, 28, w - 50, 2)
        g.append(multiline(cx, y0 + 395, cap, 28, T["muted"], anchor="middle"))
        p.append(f'<g id="card{i}">{"".join(g)}</g>')
        a.append({"sel": f"#card{i}", "fx": "pop", "dur": 0.6, "cue": cue(it)})
        if num:
            a.append({"sel": f"#v{i}", "fx": "count", "dur": 1.2, "rel": 0.4, **num})
    return "".join(p), _clean(a)


def t_bars(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    items = s.items[:5]
    n = max(1, len(items))
    nums = [parse_number(it.value) for it in items]
    vals = [x["to"] if x else 0 for x in nums]
    mx = max([abs(v) for v in vals] + [1])
    row = 470 / n
    bh = min(76, row - 28)
    y0 = 215 + (470 - row * n) / 2
    for i, it in enumerate(items):
        col = palette(T)[i % 5]
        y = y0 + i * row
        p.append(text(70, y + bh / 2 + 14, it.label or "", 38, T["ink"], id=f"bl{i}", maxw=300))
        full = 690 * (abs(vals[i]) / mx if nums[i] else 1.0)
        p.append(f'<rect id="bar{i}" x="400" y="{y}" width="{max(8, full):.1f}" height="{bh}" rx="{min(14, bh / 2)}" fill="{col}" stroke="{T["ink"]}" stroke-width="3"/>')
        p.append(text(1215, y + bh / 2 + 14, it.value if not nums[i] else "", 40, col, id=f"bv{i}", anchor="end", bold=True))
        if it.caption:
            p.append(text(70, y + bh / 2 + 44, it.caption, 24, T["muted"], id=f"bc{i}", maxw=300))
        a.append({"sel": f"#bl{i}", "fx": "wipe", "dur": 0.6, "cue": cue(it)})
        a.append({"sel": f"#bar{i}", "fx": "scalex", "dur": 1.0, "rel": 0.15, "from": 0, "to": 1, "origin": "0% 50%"})
        if nums[i]:
            a.append({"sel": f"#bv{i}", "fx": "count", "dur": 1.0, "rel": 0.0, **nums[i]})
        else:
            a.append({"sel": f"#bv{i}", "fx": "fade", "dur": 0.5, "rel": 0.6})
        if it.caption:
            a.append({"sel": f"#bc{i}", "fx": "fade", "dur": 0.5, "rel": 0.3})
    return "".join(p), _clean(a)


def t_steps(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    items = s.items[:5]
    n = max(1, len(items))
    xs = [W / 2] if n == 1 else [170 + i * (940 / (n - 1)) for i in range(n)]
    ny = 400
    for i, it in enumerate(items):
        x = xs[i]
        col = palette(T)[i % 5]
        if i > 0:
            p.append(arrow(xs[i - 1] + 52, ny, x - 52, ny, T["muted"], id=f"sa{i}", width=5))
            a.append({"sel": f"#sa{i}", "fx": "draw", "dur": 0.5, "rel": 0.35})
        g = [f'<circle cx="{x}" cy="{ny}" r="44" fill="{col}" stroke="{T["ink"]}" stroke-width="4"/>',
             text(x, ny + 16, str(i + 1), 46, T["bg"] if T.get("dark") else "#ffffff", anchor="middle", bold=True)]
        if it.icon:
            g.append(icon(x, 275, it.icon, 110, col))
        g.append(text(x, 500, it.label or "", 38, T["ink"], anchor="middle", maxw=940 / max(1, n - 1) - 20 if n > 1 else 600, bold=True))
        g.append(multiline(x, 545, wrap(it.caption, 26, (940 / max(1, n - 1) - 10) if n > 1 else 700, 2), 26, T["muted"], anchor="middle"))
        p.append(f'<g id="st{i}">{"".join(g)}</g>')
        a.append({"sel": f"#st{i}", "fx": "pop", "dur": 0.6, "cue": cue(it), "origin": "50% 40%"})
    return "".join(p), _clean(a)


def t_list(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    items = s.items[:5]
    n = max(1, len(items))
    row = min(100, 470 / n)
    y0 = 240 + (470 - row * n) / 2
    for i, it in enumerate(items):
        y = y0 + i * row
        col = palette(T)[i % 5]
        p.append(icon(105, y, it.icon or "check", 62, col if it.icon else T["good"], id=f"li{i}"))
        p.append(text(165, y + 15, it.label or "", 44, T["ink"], id=f"ll{i}", maxw=1040))
        a.append({"sel": f"#li{i}", "fx": "pop", "dur": 0.5, "cue": cue(it)})
        a.append({"sel": f"#ll{i}", "fx": "wipe", "dur": 0.8, "rel": 0.15})
    return "".join(p), _clean(a)


def t_stat(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    items = s.items[:3]
    n = max(1, len(items))
    cw = 1160 / n
    for i, it in enumerate(items):
        cx = 60 + cw * (i + 0.5)
        col = palette(T)[i % 5]
        if it.icon:
            p.append(icon(cx, 290, it.icon, 120, col, id=f"si{i}"))
            a.append({"sel": f"#si{i}", "fx": "pop", "dur": 0.6, "cue": cue(it)})
        num = parse_number(it.value)
        size = 128 if n == 1 else 96
        p.append(text(cx, 460, it.value if not num else "", size, col, id=f"sv{i}", anchor="middle", maxw=cw - 40, bold=True))
        if num:
            a.append({"sel": f"#sv{i}", "fx": "count", "dur": 1.4, "cue": None if it.icon else cue(it), "rel": 0.3 if it.icon else None, **num})
        else:
            a.append({"sel": f"#sv{i}", "fx": "pop", "dur": 0.6, "cue": None if it.icon else cue(it), "rel": 0.3 if it.icon else None})
        p.append(multiline(cx, 530, wrap(it.label, 36, cw - 60, 2), 36, T["muted"], id=f"sl{i}", anchor="middle"))
        a.append({"sel": f"#sl{i}", "fx": "wipe", "dur": 0.8, "rel": 0.5})
    return "".join(p), _clean(a)


def t_flow(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    items = s.items[:6]
    n = len(items)
    nw, nh = (200 if n == 4 else 230), 118
    if n <= 4:
        span = {1: 0, 2: 580, 3: 840, 4: 960}[n]
        xs = [W / 2 - span / 2 + i * (span / max(1, n - 1)) for i in range(n)] if n > 1 else [W / 2]
        pos = [(x, 430) for x in xs]
    else:
        top = math.ceil(n / 2)
        bot = n - top
        pos = [(200 + i * (880 / max(1, top - 1)), 300) for i in range(top)]
        pos += [(200 + i * (880 / max(1, bot - 1)) if bot > 1 else W / 2, 570) for i in range(bot)]
    for i, it in enumerate(items):
        x, y = pos[i]
        col = palette(T)[i % 5]
        g = [f'<rect x="{x - nw / 2}" y="{y - nh / 2}" width="{nw}" height="{nh}" rx="22" fill="{T["soft"]}" stroke="{col}" stroke-width="5"/>']
        if it.icon:
            lines = wrap(it.label, 28, nw - 100, 2)
            g.append(icon(x - nw / 2 + 46, y, it.icon, 60, col))
            g.append(multiline(x - nw / 2 + 86, y + 10 - (16 if len(lines) > 1 else 0), lines, 28, T["ink"], anchor="start", lh=1.15))
        else:
            lines = wrap(it.label, 32, nw - 30, 2)
            g.append(multiline(x, y + 11 - (18 if len(lines) > 1 else 0), lines, 32, T["ink"], anchor="middle", lh=1.15))
        p.append(f'<g id="fn{i}">{"".join(g)}</g>')
        a.append({"sel": f"#fn{i}", "fx": "pop", "dur": 0.55, "cue": cue(it)})
    for j, c in enumerate(s.connections[:10]):
        if not (0 <= c.source < n and 0 <= c.to < n) or c.source == c.to:
            continue
        (x1, y1), (x2, y2) = pos[c.source], pos[c.to]
        dx, dy = x2 - x1, y2 - y1
        # clip to node rectangles
        def edge(px, py, dx, dy):
            if abs(dx) * nh > abs(dy) * nw:
                k = (nw / 2 + 8) / abs(dx)
            else:
                k = (nh / 2 + 8) / abs(dy or 1)
            return px + dx * k, py + dy * k
        ax, ay = edge(x1, y1, dx, dy)
        bx, by = edge(x2, y2, -dx, -dy)
        same_row = abs(y1 - y2) < 1
        adjacent = same_row and all(abs(pos[k][1] - y1) >= 1 for k in range(min(c.source, c.to) + 1, max(c.source, c.to)))
        curve = 0 if (adjacent or not same_row) else -2 * (nh / 2 + 55)  # quadratic apex = control offset / 2
        p.append(arrow(ax, ay, bx, by, T["accent"], id=f"fc{j}", width=5, curve=curve))
        a.append({"sel": f"#fc{j}", "fx": "draw", "dur": 0.55, "cue": c.cue})
        if c.label:
            L = math.hypot(dx, dy) or 1
            nxv, nyv = -dy / L, dx / L
            mx, my = (ax + bx) / 2, (ay + by) / 2
            if curve:
                mx += nxv * (curve / 2 + (-22 if curve < 0 else 22))
                my += nyv * (curve / 2 + (-22 if curve < 0 else 22))
            else:
                my -= 22 if same_row else 0
                mx += 0 if same_row else 60
            tw = len(c.label) * 26 * _cur["k"] * _cur["w"] + 20
            p.append(f'<g id="fl{j}"><rect x="{mx - tw / 2}" y="{my - 22}" width="{tw}" height="32" rx="8" fill="{T["card"]}"/>'
                     f'{text(mx, my + 2, c.label, 26, T["accent"], anchor="middle")}</g>')
            a.append({"sel": f"#fl{j}", "fx": "fade", "dur": 0.4, "rel": 0.3})
    return "".join(p), _clean(a)


def t_compare(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    items = (s.items + [Item(), Item()])[:2]
    cols = [T["primary"], T["accent"]]
    for i, it in enumerate(items):
        x = 60 if i == 0 else 670
        col = cols[i]
        g = [f'<rect x="{x}" y="200" width="550" height="480" rx="28" fill="{T["card"]}" stroke="{col}" stroke-width="6"/>']
        cx = x + 275
        if it.icon:
            g.append(icon(cx, 290, it.icon, 120, col))
        g.append(text(cx, 400, it.label or "", 48, col, anchor="middle", maxw=500, bold=True))
        p.append(f'<g id="cp{i}">{"".join(g)}</g>')
        a.append({"sel": f"#cp{i}", "fx": "pop", "dur": 0.6, "cue": cue(it)})
        pts = [t.strip() for t in (it.caption or "").split(";") if t.strip()][:3]
        for k, pt in enumerate(pts):
            y = 455 + k * 62
            p.append(f'<g id="cb{i}{k}"><circle cx="{x + 48}" cy="{y - 10}" r="7" fill="{col}"/>'
                     f'{text(x + 70, y, pt, 30, T["ink"], maxw=450)}</g>')
            a.append({"sel": f"#cb{i}{k}", "fx": "wipe", "dur": 0.6, "rel": 0.35 if k == 0 else 0.45})
    p.append(f'<g id="vs"><circle cx="640" cy="440" r="46" fill="{T["bad"]}" stroke="{T["ink"]}" stroke-width="4"/>'
             f'{text(640, 456, "VS", 40, T["bg"] if T.get("dark") else "#ffffff", anchor="middle", bold=True)}</g>')
    a.insert(len([x for x in a if x["sel"] in ("#hd", "#sub")]) + 1, {"sel": "#vs", "fx": "pop", "dur": 0.5, "rel": 0.3})
    return "".join(p), _clean(a)


def t_callout(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    it = s.items[0] if s.items else Item(label=s.heading or "")
    warn = (it.icon or "") in ("warning", "cross", "sad", "chart-down")
    fill, stroke = ("#fdecec", T["bad"]) if warn else (T["soft"], T["primary"])
    y0 = 230 if s.heading else 190
    bh = 320
    y0 = y0 + (470 - bh) / 2 if s.heading else 200
    p.append(f'<rect id="box" x="80" y="{y0}" width="1120" height="{bh}" rx="30" fill="{fill}" stroke="{stroke}" stroke-width="6"/>')
    a.append({"sel": "#box", "fx": "pop", "dur": 0.6, "cue": cue(it), "rel": None if cue(it) else 0.4})
    tx = 150
    if it.icon:
        p.append(icon(230, y0 + bh / 2, it.icon, 170, stroke, id="cic"))
        a.append({"sel": "#cic", "fx": "pop", "dur": 0.6, "rel": 0.3})
        tx = 380
    lab = wrap(it.label, 52, 1180 - tx, 2)
    cap = wrap(it.caption, 34, 1180 - tx, 3)
    total = len(lab) * 52 * 1.2 + (len(cap) * 34 * 1.3 + 20 if cap else 0)
    y = y0 + bh / 2 - total / 2 + 44
    p.append(multiline(tx, y, lab, 52, stroke, id="clab", bold=True, lh=1.2))
    a.append({"sel": "#clab", "fx": "wipe", "dur": 1.0, "rel": 0.3})
    if cap:
        p.append(multiline(tx, y + len(lab) * 52 * 1.2 + 24, cap, 34, T["ink"], id="ccap", lh=1.3))
        a.append({"sel": "#ccap", "fx": "wipe", "dur": 1.2, "rel": 0.6})
    return "".join(p), _clean(a)


FORBIDDEN = re.compile(r"<(script|foreignObject|style|iframe|image|use)\b|href\s*=\s*\"\s*(https?:|javascript:)", re.I)


def t_diagram(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = heading(s, T)
    frag = (s.svg or "").strip()
    frag = re.sub(r"^<\?xml[^>]*>", "", frag).strip()
    frag = re.sub(r"^<svg[^>]*>|</svg>\s*$", "", frag).strip()
    if not frag or FORBIDDEN.search(frag) or not _xml_ok(frag):
        return t_list(Scene(type="list", narration=s.narration, heading=s.heading, subheading=s.subheading, items=s.items or [Item(label=s.heading or "")]), T)
    cues: list[str] = []

    def tag(m):
        cues.append(m.group(1))
        return f'<g id="dg{len(cues) - 1}" data-cue="{m.group(1)}"'

    frag = re.sub(r'<g\s+data-cue="([^"]*)"', tag, frag)
    # the player scales whatever the LLM drew into the 1100x480 content box, whatever coordinate range it used
    p.append(f'<g transform="translate(640,445)"><g data-fit="1100 470"><g id="diag">{frag}</g></g></g>')
    if cues:
        for i, c in enumerate(cues):
            a.append({"sel": f"#dg{i}", "fx": "draw", "dur": 0.9, "cue": c})
    else:
        a.append({"sel": "#diag", "fx": "draw", "dur": 2.5, "rel": 0.5})
    return "".join(p), _clean(a)


def t_outro(s: Scene, T) -> tuple[str, list[dict]]:
    p, a = [], []
    lines = wrap(hd_text(s.heading, T), 76, 1120, 2)
    p.append(multiline(W / 2, 250, lines, 76, T["primary"], id="hd", anchor="middle", lh=1.15, bold=True))
    a.append({"sel": "#hd", "fx": "wipe", "dur": 1.4, "t": 0.3})
    uy = 250 + (len(lines) - 1) * 88 + 44
    p.append(f'<path id="ul" d="M{W / 2 - 300},{uy} C{W / 2 - 150},{uy - 8} {W / 2 + 150},{uy + 8} {W / 2 + 300},{uy - 2}" fill="none" stroke="{T["accent"]}" stroke-width="8" stroke-linecap="round"/>')
    a.append({"sel": "#ul", "fx": "draw", "dur": 0.7, "rel": 1.0})
    items = s.items[:3]
    n = len(items)
    if n:
        pw = min(360, (1160 - 30 * (n - 1)) / n)
        x0 = (W - (pw * n + 30 * (n - 1))) / 2
        for i, it in enumerate(items):
            x = x0 + i * (pw + 30)
            col = palette(T)[i % 5]
            g = [f'<rect x="{x}" y="440" width="{pw}" height="120" rx="60" fill="{T["card"]}" stroke="{col}" stroke-width="5"/>']
            if it.icon:
                g.append(icon(x + 62, 500, it.icon, 64, col))
            g.append(multiline(x + (110 if it.icon else pw / 2), 510 - (12 if len(wrap(it.label, 32, pw - 130, 2)) > 1 else 0),
                               wrap(it.label, 32, pw - (130 if it.icon else 40), 2), 32, T["ink"], anchor="start" if it.icon else "middle"))
            p.append(f'<g id="rp{i}">{"".join(g)}</g>')
            a.append({"sel": f"#rp{i}", "fx": "pop", "dur": 0.55, "cue": cue(it)})
    return "".join(p), _clean(a)


# ---------------------------------------------------------------- illustrated layouts (image-model art + vector text)

def illus(x, y, w, h, url, *, id="illus", feather=False) -> str:
    """Place the illustration (1536x1024 PNG) centred in a box, preserving aspect.
    feather=True: the image is multiply-blended (paper whites disappear into the theme background) and its edges are
    softened with a blurred mask so an opaque paper image melts into the page."""
    img = (f'<image href="{esc(url)}" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" '
           f'preserveAspectRatio="xMidYMid meet"{" style=\"mix-blend-mode:multiply;filter:brightness(1.06) contrast(1.04)\"" if feather else ""}/>')
    if not feather:
        return img.replace("<image ", f'<image id="{id}" ', 1)
    mid = f"m{id}"
    inset, blur = 58, 34
    return (f'<g id="{id}"><defs>'
            f'<filter id="{mid}f" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="{blur}"/></filter>'
            f'<mask id="{mid}" maskUnits="userSpaceOnUse" x="{x - 60:.0f}" y="{y - 60:.0f}" width="{w + 120:.0f}" height="{h + 120:.0f}">'
            f'<rect x="{x + inset:.0f}" y="{y + inset:.0f}" width="{w - 2 * inset:.0f}" height="{h - 2 * inset:.0f}" rx="40" fill="#fff" filter="url(#{mid}f)"/>'
            f'</mask></defs><g mask="url(#{mid})">{img}</g></g>')


def _art_side(T, idx) -> str:
    art = L(T).get("art", "side")
    if art in ("side-right", "taped-right"):
        return "right"
    if art in ("side", "taped"):
        return "left" if idx % 2 == 0 else "right"
    if art == "center":
        return "center"
    return "top"


def tape(x, y, w, h, T) -> str:
    """Two translucent tape strips over the top corners of a picture box."""
    c = T["accent"]
    return (f'<rect x="{x - 10}" y="{y + 6}" width="110" height="26" fill="{c}" opacity=".55" transform="rotate(-28 {x + 45} {y + 19})"/>'
            f'<rect x="{x + w - 100}" y="{y + 6}" width="110" height="26" fill="{c}" opacity=".55" transform="rotate(28 {x + w - 45} {y + 19})"/>')


def i_title(s: Scene, T, url, idx=0) -> tuple[str, list[dict]]:
    p, a = [], []
    feather = T.get("feather", False)
    hs = L(T).get("heading", "left")
    if hs in ("centered-rule", "banner", "chalk") or L(T).get("art") in ("hero-top", "center"):
        # centered title, picture beneath
        lines = wrap(hd_text(s.heading, T), 76, 1100, 2)
        p.append(multiline(640, 118 - (len(lines) - 1) * 34, lines, 76, T["primary"], id="hd", anchor="middle", lh=1.1, bold=True))
        a.append({"sel": "#hd", "fx": "wipe", "dur": 1.4, "t": 0.3})
        uy = 118 + (len(lines) - 1) * 50 + 40
        if hs == "centered-rule":
            p.append(f'<path id="ul" d="M340,{uy} H940" stroke="{T["muted"]}" stroke-width="1.5"/>')
        else:
            p.append(f'<path id="ul" d="M400,{uy} C520,{uy - 8} 760,{uy + 10} 880,{uy - 2}" fill="none" stroke="{T["accent"]}" stroke-width="7" stroke-linecap="round"/>')
        a.append({"sel": "#ul", "fx": "draw", "dur": 0.7, "rel": 1.0})
        if s.subheading:
            p.append(text(640, uy + 46, s.subheading, 34, T["muted"], id="sub", anchor="middle", maxw=1000))
            a.append({"sel": "#sub", "fx": "wipe", "dur": 1.2, "rel": 0.4})
        p.append(illus(190, uy + 70, 900, 690 - (uy + 70), url, feather=feather))
        a.append({"sel": "#illus", "fx": "fade" if feather else "pop", "dur": 0.9, "rel": 0.3})
        return "".join(p), _clean(a)
    right = _art_side(T, idx) != "left"  # title: art right by default, left for side-right themes flipped
    tx, ax = (70, 670) if right else (640, 20)
    lines = wrap(hd_text(s.heading, T), 84, 600, 3)
    y0 = 300 - (len(lines) - 1) * 46
    p.append(multiline(tx, y0, lines, 84, T["primary"], id="hd", lh=1.1, bold=True))
    a.append({"sel": "#hd", "fx": "wipe", "dur": 1.4, "t": 0.3})
    uy = y0 + (len(lines) - 1) * 92 + 44
    ux2 = tx + min(600, 40 * max(len(l) for l in lines) if lines else 400)
    p.append(f'<path id="ul" d="M{tx},{uy} C{tx + 100},{uy - 8} {ux2 - 120},{uy + 10} {ux2},{uy - 2}" fill="none" stroke="{T["accent"]}" stroke-width="8" stroke-linecap="round"/>')
    a.append({"sel": "#ul", "fx": "draw", "dur": 0.7, "rel": 1.0})
    if s.subheading:
        p.append(multiline(tx, uy + 66, wrap(s.subheading, 40, 600, 3), 40, T["ink"], id="sub"))
        a.append({"sel": "#sub", "fx": "wipe", "dur": 1.2, "rel": 0.5})
    p.append(illus(ax, 60, 600, 620, url, feather=feather))
    if L(T).get("art", "").startswith("taped"):
        p.append(f'<g id="tape">{tape(ax + 60, 110, 480, 520, T)}</g>')
        a.append({"sel": "#tape", "fx": "fade", "dur": 0.3, "rel": 1.0})
    a.append({"sel": "#illus", "fx": "fade" if feather else "pop", "dur": 0.9, "rel": 0.3})
    if not feather and not L(T).get("art", "").startswith("taped"):
        a.append({"sel": "#illus", "fx": "bob", "dy": 6, "period": 3.2, "rel": 0.9})
    d, da = decor(T, idx); p += d; a += da
    return "".join(p), _clean(a)


def i_outro(s: Scene, T, url, idx=0) -> tuple[str, list[dict]]:
    p, a = [], []
    feather = T.get("feather", False)
    right = _art_side(T, idx) != "left"
    tx, ax = (70, 670) if right else (640, 20)
    lines = wrap(hd_text(s.heading, T), 68, 600, 3)
    y0 = 240 - (len(lines) - 1) * 38
    p.append(multiline(tx, y0, lines, 68, T["primary"], id="hd", lh=1.12, bold=True))
    a.append({"sel": "#hd", "fx": "wipe", "dur": 1.4, "t": 0.3})
    uy = y0 + (len(lines) - 1) * 76 + 40
    p.append(f'<path id="ul" d="M{tx},{uy} C{tx + 100},{uy - 8} {tx + 450},{uy + 10} {tx + 570},{uy - 2}" fill="none" stroke="{T["accent"]}" stroke-width="8" stroke-linecap="round"/>')
    a.append({"sel": "#ul", "fx": "draw", "dur": 0.7, "rel": 1.0})
    for i, it in enumerate(s.items[:3]):
        y = uy + 70 + i * 86
        col = palette(T)[i % 5]
        g = [f'<rect x="{tx}" y="{y - 32}" width="580" height="64" rx="{6 if L(T).get("items") == "boxes" else 32}" fill="{T["card"]}" stroke="{col}" stroke-width="4"/>']
        if it.icon:
            g.append(icon(tx + 42, y, it.icon, 42, col))
        g.append(text(tx + (80 if it.icon else 30), y + 12, it.label or "", 32, T["ink"], maxw=480))
        p.append(f'<g id="rp{i}">{"".join(g)}</g>')
        a.append({"sel": f"#rp{i}", "fx": "pop", "dur": 0.55, "cue": cue(it)})
    p.append(illus(ax, 60, 600, 620, url, feather=feather))
    a.insert(2, {"sel": "#illus", "fx": "fade" if feather else "pop", "dur": 0.9, "rel": 0.3})
    d, da = decor(T, idx); p += d; a += da
    return "".join(p), _clean(a)


def i_points(s: Scene, T, url, idx=0) -> tuple[str, list[dict]]:
    """Illustration + labelled points. Composition follows the theme layout: art left/right with a list, or a wide
    hero picture with caption columns beneath (editorial / chalkboard / blueprint / pencil)."""
    p, a = heading(s, T)
    feather = T.get("feather", False)
    items = [it for it in s.items if it.label or it.caption or it.value][:5]
    if s.type == "concept":
        items = [it for it in items if it is not (s.items[0] if s.items else None)] or items
    n = len(items)
    side = _art_side(T, idx)
    style = L(T).get("items", "list")
    numbered = s.type == "steps"

    if side == "top":
        # hero picture across the middle, captions as columns under it
        top = 150 if not s.subheading else 180
        ah = 350 if n else 520
        p.append(illus(140, top, 1000, ah, url, feather=feather))
        a.append({"sel": "#illus", "fx": "fade" if feather else "pop", "dur": 0.9, "rel": 0.4})
        if n:
            cw = 1120 / n
            for i, it in enumerate(items):
                cx = 80 + cw * (i + 0.5)
                col = palette(T)[i % 5]
                y = top + ah + 48
                g = []
                lab = hd_text(it.label or "", T) if T.get("uppercase") else (it.label or "")
                prefix = f"{i + 1}.  " if numbered else ""
                if it.icon and not numbered:
                    g.append(icon(cx, y - 10, it.icon, 40, col))
                    y += 36
                g.append(text(cx, y, prefix + lab + (f"  {it.value}" if it.value else ""), 28, T["primary"], anchor="middle", maxw=cw - 24, bold=True))
                if it.caption:
                    g.append(multiline(cx, y + 30, wrap(it.caption, 22, cw - 30, 2), 22, T["muted"], anchor="middle", lh=1.2))
                if L(T).get("decor") == "editorial":
                    g.append(f'<path d="M{cx - cw / 2 + 24:.0f},{top + ah + 18} H{cx + cw / 2 - 24:.0f}" stroke="{T["muted"]}" stroke-width="1"/>')
                p.append(f'<g id="pt{i}">{"".join(g)}</g>')
                a.append({"sel": f"#pt{i}", "fx": "fade", "dur": 0.6, "cue": cue(it)})
        d, da = decor(T, idx); p += d; a += da
        return "".join(p), _clean(a)

    taped = L(T).get("art", "").startswith("taped")
    if side == "center":
        # big picture in the middle, items arranged around / beneath it
        p.append(illus(300, 130, 680, 330, url, feather=feather))
        a.append({"sel": "#illus", "fx": "fade" if feather else "pop", "dur": 0.9, "rel": 0.4})
        if style == "pills" and n:
            pw = min(270, (1160 - 20 * (n - 1)) / n); x0 = 640 - (pw * n + 20 * (n - 1)) / 2
            for i, it in enumerate(items):
                x = x0 + i * (pw + 20); col = palette(T)[i % 5]
                g = [f'<rect x="{x}" y="500" width="{pw}" height="72" rx="36" fill="none" stroke="{col}" stroke-width="4"/>']
                if numbered:
                    g.append(f'<circle cx="{x + 36}" cy="536" r="18" fill="{col}"/>' + text(x + 36, 545, str(i + 1), 24, T["bg"], anchor="middle", bold=True))
                elif it.icon:
                    g.append(icon(x + 36, 536, it.icon, 34, col))
                g.append(text(x + 66, 545, (it.label or "") + (f" {it.value}" if it.value else ""), 28, col, maxw=pw - 80, bold=True))
                if it.caption:
                    g.append(text(x + pw / 2, 612, it.caption, 22, T["muted"], anchor="middle", maxw=pw))
                p.append(f'<g id="pt{i}">{"".join(g)}</g>')
                a.append({"sel": f"#pt{i}", "fx": "pop", "dur": 0.5, "cue": cue(it)})
        elif style == "tags" and n:
            tw = min(260, (1160 - 24 * (n - 1)) / n); x0 = 640 - (tw * n + 24 * (n - 1)) / 2
            for i, it in enumerate(items):
                x = x0 + i * (tw + 24); col = palette(T)[i % 5]
                g = [f'<path d="M{x},496 H{x + tw} V560 L{x + tw / 2},578 L{x},560 Z" fill="{col}" stroke="{T["ink"]}" stroke-width="3"/>',
                     f'<rect x="{x}" y="496" width="{tw}" height="16" fill="{T["ink"]}" opacity=".18"/>',
                     text(x + tw / 2, 544, hd_text(it.label or "", T) if T.get("uppercase") else (it.label or ""), 26, "#ffffff", anchor="middle", maxw=tw - 20, bold=True)]
                if it.value:
                    g.append(text(x + tw / 2, 606, it.value, 30, col, anchor="middle", maxw=tw, bold=True))
                elif it.caption:
                    g.append(text(x + tw / 2, 606, it.caption, 22, T["muted"], anchor="middle", maxw=tw))
                p.append(f'<g id="pt{i}">{"".join(g)}</g>')
                a.append({"sel": f"#pt{i}", "fx": "slide", "dy": -30, "dur": 0.5, "cue": cue(it)})
        elif n:  # callouts around the picture with leader lines
            slots = [(60, 230, "L"), (60, 520, "L"), (1220, 230, "R"), (1220, 520, "R"), (640, 640, "B")][:n]
            for i, (it, (x, y, sd)) in enumerate(zip(items, slots)):
                col = palette(T)[i % 5]; anchor = {"L": "start", "R": "end", "B": "middle"}[sd]
                lab = (it.label or "") + (f"  {it.value}" if it.value else "")
                g = [text(x, y, lab, 40, T["primary"], anchor=anchor, maxw=230, bold=True)]
                if it.caption:
                    g.append(multiline(x, y + 36, wrap(it.caption, 24, 230, 2), 24, T["muted"], anchor=anchor))
                est = min(230, len(lab) * 40 * _cur["k"] * _cur["w"]) + 16
                if sd == "L":
                    x1, x2, y2 = x + est, 330, (y - 14 if y < 400 else 440)
                elif sd == "R":
                    x1, x2, y2 = x - est, 950, (y - 14 if y < 400 else 440)
                else:
                    x1, x2, y2 = x, x, 470
                g.append(f'<path d="M{x1:.0f},{y - 14} L{x2},{y2}" fill="none" stroke="{col}" stroke-width="3" stroke-dasharray="3 9" stroke-linecap="round"/>'
                         f'<circle cx="{x2}" cy="{y2}" r="6" fill="{col}"/>')
                p.append(f'<g id="pt{i}">{"".join(g)}</g>')
                a.append({"sel": f"#pt{i}", "fx": "fade", "dur": 0.6, "cue": cue(it)})
        d, da = decor(T, idx); p += d; a += da
        return "".join(p), _clean(a)

    ax = 30 if side == "left" else 640
    lx = 676 if side == "left" else (130 if T.get("background") == "notebook" else 60)
    p.append(illus(ax, 150, 610, 560, url, feather=feather))
    if taped:
        p.append(f'<g id="tape">{tape(ax + 60, 190, 490, 480, T)}</g>')
    a.append({"sel": "#illus", "fx": "fade" if feather else "pop", "dur": 0.9, "rel": 0.4})
    if taped:
        a.append({"sel": "#tape", "fx": "fade", "dur": 0.3, "rel": 0.6})
    if not n:
        d, da = decor(T, idx); p += d; a += da
        return "".join(p), _clean(a)

    if style == "grid":  # 2x2 small cards with thin dividers (infographic)
        cols = 2 if n > 2 else 1; rows = (n + cols - 1) // cols
        cw, ch = (560 - 16 * (cols - 1)) / cols, min(200, (470 - 16 * (rows - 1)) / rows)
        y0 = 215 + (470 - (ch * rows + 16 * (rows - 1))) / 2
        for i, it in enumerate(items):
            x = lx + (i % cols) * (cw + 16); y = y0 + (i // cols) * (ch + 16); col = palette(T)[i % 5]
            g = [f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="6" fill="{T["card"]}" stroke="{T["muted"]}" stroke-width="1.5"/>']
            if numbered:
                g.append(text(x + 18, y + 40, f"{i + 1:02d}", 26, col, bold=True))
            elif it.icon:
                g.append(icon(x + 36, y + 36, it.icon, 40, col))
            g.append(text(x + 18, y + ch / 2 + 14, (it.label or "") + (f"  {it.value}" if it.value else ""), 30, T["ink"], maxw=cw - 36, bold=True))
            if it.caption:
                g.append(text(x + 18, y + ch - 20, it.caption, 20, T["muted"], maxw=cw - 36))
            p.append(f'<g id="pt{i}">{"".join(g)}</g>')
            a.append({"sel": f"#pt{i}", "fx": "fade", "dur": 0.5, "cue": cue(it)})
    elif style == "table":  # drafting title-block: rows separated by thin lines, index column
        rh = min(90, 470 / n); y0 = 215 + (470 - rh * n) / 2
        p.append(f'<rect x="{lx}" y="{y0}" width="560" height="{rh * n}" fill="none" stroke="{T["primary"]}" stroke-width="2"/>')
        for i, it in enumerate(items):
            y = y0 + i * rh; col = palette(T)[i % 5]
            g = [f'<path d="M{lx},{y + rh} H{lx + 560} M{lx + 70},{y} V{y + rh}" stroke="{T["primary"]}" stroke-width="1.2" fill="none"/>',
                 text(lx + 35, y + rh / 2 + 10, f"{i + 1:02d}" if numbered else "•", 26, col, anchor="middle", bold=True),
                 text(lx + 90, y + rh / 2 - (6 if it.caption and rh > 60 else -10), hd_text(it.label or "", T) + (f"  {it.value}" if it.value else ""), 28, T["ink"], maxw=450, bold=True)]
            if it.caption and rh > 60:
                g.append(text(lx + 90, y + rh / 2 + 24, it.caption, 20, T["muted"], maxw=450))
            p.append(f'<g id="pt{i}">{"".join(g)}</g>')
            a.append({"sel": f"#pt{i}", "fx": "fade", "dur": 0.5, "cue": cue(it)})
    elif style == "checklist":  # handwritten to-do on the ruled lines
        rh = 72; y0 = 251 + (470 - rh * n) / 2; y0 = 165.5 + 36 * round((y0 - 165.5) / 36)  # baselines sit on the rules
        for i, it in enumerate(items):
            y = y0 + i * rh; col = palette(T)[i % 5]
            g = [f'<rect x="{lx + 4}" y="{y - 24}" width="30" height="30" rx="4" fill="{T["card"]}" stroke="{T["ink"]}" stroke-width="2.5"/>',
                 f'<path class="tick" d="M{lx + 8},{y - 10} l10,12 l20,-26" fill="none" stroke="{T["secondary"]}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>',
                 f'<rect x="{lx + 46}" y="{y - 26}" width="{min(480, len((it.label or "") + (it.value or "")) * 22 + 24)}" height="34" fill="{T["accent"]}" opacity=".55" rx="3"/>' if i == 0 else "",
                 text(lx + 54, y, (it.label or "") + (f"  {it.value}" if it.value else ""), 40, T["primary"], maxw=490, cls="script")]
            if it.caption:
                g.append(text(lx + 52, y + 30, it.caption, 22, T["muted"], maxw=490))
            p.append(f'<g id="pt{i}">{"".join(g)}</g>')
            a.append({"sel": f"#pt{i}", "fx": "fade", "dur": 0.4, "cue": cue(it)})
            a.append({"sel": f"#pt{i} .tick", "fx": "draw", "dur": 0.4, "rel": 0.3})
    elif style == "bubbles":  # tilted speech bubbles pointing at the picture
        bh = min(96, 470 / n - 10); y0 = 215 + (470 - (bh + 10) * n) / 2 + 10
        for i, it in enumerate(items):
            y = y0 + i * (bh + 10); col = palette(T)[i % 5]; rot = (-2.5, 2, -1.5, 2.5, -2)[i % 5]
            tail = f'M{lx + 540},{y + bh / 2 - 10} l24,10 l-24,10' if side == "right" else f'M{lx + 20},{y + bh / 2 - 10} l-24,10 l24,10'
            g = [f'<g transform="rotate({rot} {lx + 280} {y + bh / 2})"><rect x="{lx + 20}" y="{y}" width="520" height="{bh}" rx="{bh / 2}" fill="{T["card"]}" stroke="{col}" stroke-width="4"/>'
                 f'<path d="{tail} Z" fill="{T["card"]}" stroke="{col}" stroke-width="4" stroke-linejoin="round"/>']
            if it.icon and not numbered:
                g.append(icon(lx + 62, y + bh / 2, it.icon, 40, col))
            elif numbered:
                g.append(f'<circle cx="{lx + 62}" cy="{y + bh / 2}" r="20" fill="{col}"/>' + text(lx + 62, y + bh / 2 + 9, str(i + 1), 26, "#fff", anchor="middle", bold=True))
            g.append(text(lx + 100, y + bh / 2 + (0 if it.caption else 11), (it.label or "") + (f"  {it.value}" if it.value else ""), 30, T["ink"], maxw=420, bold=True))
            if it.caption:
                g.append(text(lx + 100, y + bh / 2 + 28, it.caption, 21, T["muted"], maxw=420))
            g.append("</g>")
            p.append(f'<g id="pt{i}">{"".join(g)}</g>')
            a.append({"sel": f"#pt{i}", "fx": "pop", "dur": 0.5, "cue": cue(it)})
    else:
        row = min(104, 470 / n)
        y0 = 215 + (470 - row * n) / 2 + 20
        for i, it in enumerate(items):
            y = y0 + i * row
            col = palette(T)[i % 5]
            g = []
            lab = it.label or ""
            if it.value:
                lab = f"{lab}  {it.value}" if lab else it.value
            if style == "boxes":
                bh = min(row - 12, 86)
                g.append(f'<rect x="{lx}" y="{y - bh / 2 - 8}" width="560" height="{bh}" rx="{4 if L(T).get("decor") == "pixels" else 10}" fill="{T["card"]}" stroke="{col}" stroke-width="4"/>')
                if numbered:
                    g.append(f'<rect x="{lx}" y="{y - bh / 2 - 8}" width="54" height="{bh}" fill="{col}"/>' + text(lx + 27, y + 2, str(i + 1), 28, T["bg"] if T.get("dark") else "#fff", anchor="middle", bold=True))
                elif it.icon:
                    g.append(icon(lx + 32, y - 8, it.icon, 38, col))
                tx0 = lx + 70
                g.append(text(tx0, y - (6 if it.caption and bh > 60 else -2), lab, 30, T["ink"], maxw=560 - 90, bold=True))
                if it.caption and bh > 60:
                    g.append(text(tx0, y + 24, it.caption, 22, T["muted"], maxw=560 - 90))
            else:
                if numbered:
                    g.append(f'<circle cx="{lx}" cy="{y - 10}" r="22" fill="{col}" stroke="{T["ink"]}" stroke-width="3"/>'
                             + text(lx, y - 1, str(i + 1), 26, T["bg"] if T.get("dark") else "#ffffff", anchor="middle", bold=True))
                elif it.icon:
                    g.append(icon(lx, y - 10, it.icon, 44, col))
                else:
                    g.append(f'<circle cx="{lx}" cy="{y - 10}" r="9" fill="{col}"/>')
                g.append(text(lx + 44, y, lab, 36, T["ink"], maxw=500, bold=bool(it.value or n <= 3)))
                if it.caption and row >= 70:
                    g.append(text(lx + 44, y + 32, it.caption, 24, T["muted"], maxw=500))
            p.append(f'<g id="pt{i}">{"".join(g)}</g>')
            a.append({"sel": f"#pt{i}", "fx": "slide", "dx": 40 if side == "left" else -40, "dur": 0.6, "cue": cue(it)})
    d, da = decor(T, idx); p += d; a += da
    return "".join(p), _clean(a)


def i_side(s: Scene, T, url, inner) -> tuple[str, list[dict]]:
    """Keep a data template (bars/stat/compare/flow/diagram) but tuck a smaller illustration into free space."""
    svg, anims = inner(s, T)
    if s.type in ("bars", "stat"):
        return svg, anims  # these use the full width; no room for art
    return svg, anims


ILLUSTRATED = {"title": i_title, "outro": i_outro, "concept": i_points, "cards": i_points, "steps": i_points,
               "list": i_points, "callout": i_points}

TEMPLATES = {
    "title": t_title, "concept": t_concept, "cards": t_cards, "bars": t_bars, "steps": t_steps, "list": t_list,
    "stat": t_stat, "flow": t_flow, "compare": t_compare, "callout": t_callout, "diagram": t_diagram, "outro": t_outro,
}


def render_scene(scene: Scene, T: dict, image_url: str | None = None, idx: int = 0) -> tuple[str, list[dict]]:
    set_font_metrics(T)
    if image_url and scene.type in ILLUSTRATED:
        return ILLUSTRATED[scene.type](scene, T, image_url, idx)
    fn = TEMPLATES.get(scene.type, t_list)
    svg, anims = fn(scene, T)
    if scene.type not in ("title", "outro"):
        d, da = decor(T, idx)
        svg += "".join(d); anims = anims + da
    return svg, anims


def _clean(anims: list[dict]) -> list[dict]:
    out = []
    for a in anims:
        a = {k: v for k, v in a.items() if v is not None}
        out.append(a)
    return out


def _xml_ok(frag: str) -> bool:
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{frag}</svg>')
        return True
    except ET.ParseError:
        return False
