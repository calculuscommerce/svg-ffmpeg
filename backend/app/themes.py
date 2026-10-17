"""Visual themes.

A theme is a token table the scene templates read (colours, card fill, highlight/uppercase headings) plus
presentation the player applies at render time: background, fonts, stroke filter, icon ink and preferred hand.
Every template reads colours from here so a video looks like one system.
"""
from __future__ import annotations

from .models import Item, Scene


def _t(name, title, description, *, primary, secondary, accent, good="#2e8b57", bad="#d64545", ink="#222222",
       muted="#5b6472", soft="#e9f1fb", bg="#fdfcfa", card="#ffffff", font_head="hand", font_body="hand",
       background="plain", filter="wobble", mono=False, highlight=False, uppercase=False, hand="marker",
       stroke_scale=1.0, dark=False, swatch=None, no_images=False, pixel=False):
    return dict(no_images=no_images, pixel=pixel, name=name, title=title, description=description, primary=primary, secondary=secondary, accent=accent,
                good=good, bad=bad, ink=ink, muted=muted, soft=soft, bg=bg, card=card, font_head=font_head,
                font_body=font_body, background=background, filter=filter, mono=mono, highlight=highlight,
                uppercase=uppercase, hand=hand, stroke_scale=stroke_scale, dark=dark,
                swatch=swatch or [primary, accent, bg])


THEMES = {t["name"]: t for t in [
    _t("hand-drawn", "Hand Drawn", "Friendly whiteboard sketch with colourful markers.",
       primary="#1f4aa8", secondary="#5aa9e6", accent="#e08a1e"),
    _t("classic-whiteboard", "Classic Whiteboard", "The original look: marker lettering and the built-in vector drawings, no AI art.",
       primary="#1f4aa8", secondary="#5aa9e6", accent="#e08a1e", no_images=True),
    _t("hand-vector", "Hand Vector", "Clean single-weight line icons, restrained palette.",
       primary="#1b2a41", secondary="#4a6fa5", accent="#1b2a41", good="#2f6f4e", bad="#8c2f2f", muted="#6b7280",
       soft="#f1f3f6", bg="#ffffff", filter="none", font_head="kalam", font_body="kalam"),
    _t("bold-marker", "Bold Marker", "Thick marker lettering with highlighter boxes.",
       primary="#d1495b", secondary="#1f4aa8", accent="#f6c445", good="#2e8b57", bad="#b32d2d", bg="#fffdf7",
       font_head="marker", font_body="hand", highlight=True, stroke_scale=1.25),
    _t("chalkboard", "ChalkBoard", "White chalk on a dark green board.",
       primary="#f4f1e8", secondary="#f6d365", accent="#9be3c8", good="#9be3c8", bad="#f4a59a", ink="#f4f1e8",
       muted="#c9c4b4", soft="#2f4a3f", bg="#1f3b32", card="#2a4639", background="chalkboard", filter="chalk",
       mono=False, hand="chalk", dark=True, font_head="hand", font_body="hand"),
    _t("editorial-monochrome", "Editorial Monochrome", "Serif typography, grey tones, understated.",
       primary="#1a1a1a", secondary="#555555", accent="#8a7f72", good="#3a3a3a", bad="#1a1a1a", ink="#1a1a1a",
       muted="#6f6f6f", soft="#efece6", bg="#f7f4ee", card="#fbf9f4", font_head="serif", font_body="serif",
       filter="none", mono=True, background="paper"),
    _t("voxel-arcade", "Voxel Arcade", "16-bit pixel art: chunky white and yellow headlines on cobalt blue.",
       primary="#ffffff", secondary="#ffd43b", accent="#ff8c42", good="#7ed957", bad="#ff5d5d", ink="#ffffff",
       muted="#cfe0ff", soft="#173f9c", bg="#1f56d6", card="#173f9c", font_head="pixel", font_body="pixel",
       filter="none", background="pixelgrid", uppercase=True, dark=True, hand="none", pixel=True),
    _t("retro-mint", "Retro Mint", "Mint paper, label boxes and warm accents.",
       primary="#2f5d50", secondary="#e07a3f", accent="#f2c14e", good="#2f5d50", bad="#c44536", ink="#2b3a33",
       muted="#5f7369", soft="#dfeee3", bg="#e9f4e4", card="#fbfaf2", font_head="oswald", font_body="hand",
       highlight=True, filter="wobble", background="paper"),
    _t("documentary-blueprint", "Documentary Blueprint", "White technical lines on blueprint blue.",
       primary="#ffffff", secondary="#cfe3ff", accent="#ffd166", good="#cfe3ff", bad="#ffb4a2", ink="#ffffff",
       muted="#b8cdee", soft="#1f4f9e", bg="#163f86", card="#1f4f9e", font_head="architect", font_body="architect",
       filter="none", background="blueprint", uppercase=True, dark=True, hand="pencil"),
    _t("neon", "Neon", "Glowing neon strokes on black.",
       primary="#39ff14", secondary="#00e5ff", accent="#ff2bd6", good="#39ff14", bad="#ff2bd6", ink="#f2f2f2",
       muted="#9aa5b1", soft="#141414", bg="#0b0b0f", card="#141420", font_head="marker", font_body="hand",
       filter="neon", background="dark", dark=True, hand="none"),
    _t("doodle-color-pop", "Doodle Color Pop", "Playful doodles, bright colours, lots of energy.",
       primary="#ff5d8f", secondary="#5aa9e6", accent="#ffbe0b", good="#06d6a0", bad="#ef476f", bg="#ffffff",
       font_head="caveat", font_body="hand", filter="wobble", stroke_scale=1.15),
    _t("notebook", "Notebook", "Spiral notebook: blue ballpoint handwriting on ruled paper, red pen ticks, highlighter.",
       primary="#1d4ed8", secondary="#d1495b", accent="#ffe066", good="#2e8b57", bad="#d1495b", ink="#1f2a44",
       muted="#6b7a92", soft="#fff7bf", bg="#fbfaf3", card="#fff7bf", background="notebook", filter="wobble",
       font_head="caveat", font_body="hand", hand="pencil"),
    _t("pencil", "Pencil", "Soft graphite sketch, greys only.",
       primary="#3a3a3a", secondary="#6a6a6a", accent="#3a3a3a", good="#3a3a3a", bad="#3a3a3a", ink="#2e2e2e",
       muted="#7a7a7a", soft="#eeeeee", bg="#fafafa", card="#ffffff", filter="pencil", mono=True, hand="pencil",
       stroke_scale=0.8),
    # legacy names kept so older projects still render
    _t("ocean", "Ocean", "Blue and orange whiteboard.", primary="#1f4aa8", secondary="#5aa9e6", accent="#e08a1e"),
    _t("forest", "Forest", "Green whiteboard.", primary="#2e7d32", secondary="#7cc85a", accent="#e08a1e", soft="#eaf7e0"),
    _t("sunset", "Sunset", "Warm red and orange.", primary="#d1495b", secondary="#f0a030", accent="#1f4aa8", bad="#b32d2d", soft="#fdeeea"),
    _t("berry", "Berry", "Purple and gold.", primary="#6a3fb5", secondary="#b388eb", accent="#f0a030", soft="#f1ebfb"),
    _t("slate", "Slate", "Charcoal and yellow.", primary="#2c3e50", secondary="#7f8c8d", accent="#f1c40f", good="#27ae60", bad="#e74c3c", soft="#eef1f4"),
    _t("marker", "Black Marker", "Black ink on white, like a real whiteboard.", primary="#111111", secondary="#444444",
       accent="#111111", good="#222222", bad="#111111", ink="#111111", muted="#555555", soft="#f3f3f3", bg="#ffffff", mono=True),
]}

# Locked art-direction prompt per theme for the image model. Subject brief is appended; "no text" is enforced globally.
STYLES = {
    "classic-whiteboard": "unused",
    "hand-drawn": "Hand-drawn whiteboard explainer illustration: bold black marker outlines, flat bright colour fills (blue, yellow, green, coral), slight hand-drawn wobble, small doodle accents like stars and squiggles, playful and clean.",
    "hand-vector": "Clean monoline vector icon illustration: single-weight dark navy outlines, minimal muted fills (navy, slate blue, white), geometric, lots of white space, modern infographic style.",
    "bold-marker": "Bold thick marker illustration: heavy black outlines, saturated poster colours (red, yellow, blue, green), chunky shapes, energetic, highlighter-style accents.",
    "chalkboard": "Chalk drawing on a dark green chalkboard: white and pastel chalk strokes (cream, soft yellow, mint), slightly dusty and grainy, textured chalk shading, classroom feel.",
    "editorial-monochrome": "Fine black ink and graphite editorial illustration in the manner of a premium broadsheet newspaper feature: realistic, well-proportioned people with warm natural expressions, rendered with dense fine parallel hatching and crosshatching, crisp confident contour lines, DEEP rich blacks and strong contrast — dense dark hatching in the shadows, clothing and hair, bright paper left for highlights — so the drawing reads bold and finished, never faint or pale. Strictly neutral monochrome — black, cool greys and white, absolutely no sepia or colour tint — on plain pure white paper. Figures are three-quarter length and fade softly into the paper at the bottom like an unfinished vignette, with generous empty paper around them. No background scenery. Short realistic text on device screens or signs is fine where natural.",
    "voxel-arcade": "Clean 16-bit pixel art in the style of a modern indie game cutscene: a friendly cartoon character with a big expressive face, brown hair and a green hoodie, thick dark outlines, bold saturated colours (greens, oranges, yellows, warm browns), crisp visible square pixels, simple props drawn as chunky sprites. Flat, perfectly even cobalt blue background with nothing else behind the subject.",
    "retro-mint": "Mid-century retro illustration: mint green, mustard yellow, burnt orange and dark teal, flat textured shapes, slight print grain, label-box poster style from the 1950s.",
    "documentary-blueprint": "Technical blueprint drawing: thin white and pale blue line work, dashed construction lines and dimension marks, drafting style on deep blueprint blue.",
    "neon": "Neon sign illustration: glowing tube-light strokes in electric green, cyan and magenta on black, soft outer glow, minimal filled shapes.",
    "doodle-color-pop": "Playful colourful doodle illustration: loose hand-drawn lines, bright pop colours (pink, yellow, cyan, orange), motion lines, sparkles and stars, fun and energetic.",
    "notebook": "Blue ballpoint pen sketch with coloured pencil shading, drawn directly on plain cream paper: confident ink outlines, loose hatching, a few highlighter-yellow and red-pen accents, charming student-notebook doodle feel, lots of empty paper around the subject.",
    "pencil": "Graphite pencil sketch with a full tonal range: dark 6B shadows and crisp HB contours, confident hatching, visible pencil texture, no colour, sketchbook style on pure white paper.",
    "marker": "Black whiteboard marker drawing: pure black ink strokes on white, no colour, confident hand-drawn lines, light grey hatching for shadows.",
}
for _n in ("ocean", "forest", "sunset", "berry", "slate"):
    STYLES[_n] = STYLES["hand-drawn"]

# Per-theme image generation options: opaque paper (feathered into the theme bg) vs transparent cutout; quality tier;
# whether short text on screens/signs is allowed in the picture.
IMAGE_OPTS = {
    "editorial-monochrome": dict(background="opaque", paper="#ffffff", quality="high", screen_text=True, feather=True),
    "pencil": dict(background="opaque", paper="#ffffff", quality="medium", screen_text=False, feather=True),
    "notebook": dict(background="opaque", paper="#ffffff", quality="medium", screen_text=False, feather=True),
    "voxel-arcade": dict(background="opaque", paper="#1f56d6", quality="medium", screen_text=True, feather="mask", key_bg="#1f56d6"),
}
DEFAULT_IMAGE_OPTS = dict(background="transparent", paper=None, quality=None, screen_text=False, feather=False)

for _n, _o in IMAGE_OPTS.items():
    THEMES[_n]["feather"] = _o.get("feather") or False

# Layout personality per theme — the composition grammar, so themes don't read as recolours of one page.
#   heading: left | underline | centered-rule | banner | rule-double | chalk | label
#   art:     side (alternates left/right by scene) | hero-top (wide picture, caption columns beneath) | side-right
#   items:   list | boxes | columns
#   decor:   doodles | editorial | pixels | corners | sticky | none
LAYOUTS = {
    #                         heading          art          items        decor
    "classic-whiteboard":    dict(heading="left",          art="side",       items="list",      decor="none"),
    "hand-drawn":            dict(heading="underline",     art="side",       items="list",      decor="doodles", frame="whiteboard"),
    "hand-vector":           dict(heading="left",          art="side-right", items="grid",      decor="none"),
    "bold-marker":           dict(heading="label",         art="side",       items="boxes",     decor="doodles"),
    "chalkboard":            dict(heading="chalk",         art="hero-top",   items="columns",   decor="none"),
    "editorial-monochrome":  dict(heading="centered-rule", art="hero-top",   items="columns",   decor="editorial"),
    "voxel-arcade":          dict(heading="arcade",        art="side",       items="boxes",     decor="pixels"),
    "retro-mint":            dict(heading="label",         art="center",     items="tags",      decor="none"),
    "documentary-blueprint": dict(heading="rule-double",   art="side",       items="table",     decor="corners"),
    "neon":                  dict(heading="centered-rule", art="center",     items="pills",     decor="none"),
    "doodle-color-pop":      dict(heading="underline",     art="side-right", items="bubbles",   decor="doodles"),
    "notebook":              dict(heading="ink",           art="taped-right", items="checklist", decor="sticky"),
    "pencil":                dict(heading="left",          art="taped",      items="list",      decor="none"),
    "marker":                dict(heading="underline",     art="center",     items="callouts",  decor="none"),
}
for _n, _l in LAYOUTS.items():
    THEMES[_n]["layout"] = _l
for _n in ("ocean", "forest", "sunset", "berry", "slate"):
    THEMES[_n]["layout"] = LAYOUTS["hand-drawn"]

GALLERY = ["hand-drawn", "classic-whiteboard", "hand-vector", "bold-marker", "chalkboard", "editorial-monochrome", "voxel-arcade",
           "retro-mint", "documentary-blueprint", "neon", "doodle-color-pop", "notebook", "pencil", "marker"]
DEFAULT_THEME = "hand-drawn"


def theme(name: str | None) -> dict:
    return THEMES.get((name or "").lower(), THEMES[DEFAULT_THEME])


def player_theme(T: dict) -> dict:
    """The subset the player needs at render time."""
    d = {k: T[k] for k in ("bg", "ink", "primary", "accent", "muted", "font_head", "font_body", "background",
                           "filter", "mono", "hand", "stroke_scale", "dark")}
    d["frame"] = (T.get("layout") or {}).get("frame")
    d["pixel"] = bool(T.get("pixel"))
    return d


# One fixed demo scene rendered in every theme for the gallery thumbnails.
DEMO_SCENE = Scene(
    type="steps", illustration="A young creator sits at a desk sketching ideas in an open notebook, a glowing lightbulb floating above their head, and a laptop beside them showing a video player with a play button", narration="You start with an idea, turn it into a script, and it becomes a video you can share.",
    heading="How ideas become videos",
    items=[Item(icon="lightbulb", label="Idea", caption="Spark it", cue="idea"),
           Item(icon="document", label="Script", caption="Write it down", cue="script"),
           Item(icon="camera", label="Video", caption="Render it", cue="video"),
           Item(icon="megaphone", label="Share", caption="Grow", cue="share")],
)
