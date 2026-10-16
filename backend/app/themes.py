"""Colour themes. Every scene template reads colours from here so a video looks like one system."""

THEMES = {
    "ocean": dict(primary="#1f4aa8", secondary="#5aa9e6", accent="#e08a1e", good="#2e8b57", bad="#d64545",
                  ink="#222222", muted="#5b6472", soft="#e9f1fb", bg="#fdfcfa"),
    "forest": dict(primary="#2e7d32", secondary="#7cc85a", accent="#e08a1e", good="#2e8b57", bad="#d64545",
                   ink="#222222", muted="#5b6472", soft="#eaf7e0", bg="#fdfcfa"),
    "sunset": dict(primary="#d1495b", secondary="#f0a030", accent="#1f4aa8", good="#2e8b57", bad="#b32d2d",
                   ink="#222222", muted="#6b5b5b", soft="#fdeeea", bg="#fdfcfa"),
    "berry": dict(primary="#6a3fb5", secondary="#b388eb", accent="#f0a030", good="#2e8b57", bad="#d64545",
                  ink="#222222", muted="#5b5472", soft="#f1ebfb", bg="#fdfcfa"),
    "slate": dict(primary="#2c3e50", secondary="#7f8c8d", accent="#f1c40f", good="#27ae60", bad="#e74c3c",
                  ink="#1b1b1b", muted="#5b6472", soft="#eef1f4", bg="#fdfcfa"),
    # black marker on a whiteboard (RSA-Animate / VideoScribe look); the player also desaturates icons
    "marker": dict(primary="#111111", secondary="#444444", accent="#111111", good="#222222", bad="#111111",
                   ink="#111111", muted="#555555", soft="#f3f3f3", bg="#ffffff", mono=True),
}

DEFAULT_THEME = "ocean"


def theme(name: str | None) -> dict:
    return THEMES.get((name or "").lower(), THEMES[DEFAULT_THEME])
