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
       stroke_scale=1.0, dark=False, swatch=None):
    return dict(name=name, title=title, description=description, primary=primary, secondary=secondary, accent=accent,
                good=good, bad=bad, ink=ink, muted=muted, soft=soft, bg=bg, card=card, font_head=font_head,
                font_body=font_body, background=background, filter=filter, mono=mono, highlight=highlight,
                uppercase=uppercase, hand=hand, stroke_scale=stroke_scale, dark=dark,
                swatch=swatch or [primary, accent, bg])


THEMES = {t["name"]: t for t in [
    _t("hand-drawn", "Hand Drawn", "Friendly whiteboard sketch with colourful markers.",
       primary="#1f4aa8", secondary="#5aa9e6", accent="#e08a1e"),
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
    _t("voxel-arcade", "Voxel Arcade", "Pixel font, blocky shapes, arcade blue.",
       primary="#ffd43b", secondary="#5aa9e6", accent="#ff8c42", good="#7ed957", bad="#ff5d5d", ink="#ffffff",
       muted="#b9d3f0", soft="#1b3f8f", bg="#142f73", card="#1b3f8f", font_head="pixel", font_body="pixel",
       filter="none", background="pixelgrid", uppercase=True, dark=True, hand="none"),
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
    _t("notebook", "Notebook", "Ruled paper, pen sketches, sticky-note colours.",
       primary="#1f4aa8", secondary="#d1495b", accent="#f6c445", ink="#23324a", muted="#60708a", soft="#eef3ff",
       bg="#fbfbf6", card="#fffdf0", background="notebook", filter="pencil", hand="pencil"),
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

GALLERY = ["hand-drawn", "hand-vector", "bold-marker", "chalkboard", "editorial-monochrome", "voxel-arcade",
           "retro-mint", "documentary-blueprint", "neon", "doodle-color-pop", "notebook", "pencil", "marker"]
DEFAULT_THEME = "hand-drawn"


def theme(name: str | None) -> dict:
    return THEMES.get((name or "").lower(), THEMES[DEFAULT_THEME])


def player_theme(T: dict) -> dict:
    """The subset the player needs at render time."""
    return {k: T[k] for k in ("bg", "ink", "primary", "accent", "muted", "font_head", "font_body", "background",
                               "filter", "mono", "hand", "stroke_scale", "dark")}


# One fixed demo scene rendered in every theme for the gallery thumbnails.
DEMO_SCENE = Scene(
    type="steps", narration="You start with an idea, turn it into a script, and it becomes a video you can share.",
    heading="How ideas become videos",
    items=[Item(icon="lightbulb", label="Idea", caption="Spark it", cue="idea"),
           Item(icon="document", label="Script", caption="Write it down", cue="script"),
           Item(icon="camera", label="Video", caption="Render it", cue="video"),
           Item(icon="megaphone", label="Share", caption="Grow", cue="share")],
)
