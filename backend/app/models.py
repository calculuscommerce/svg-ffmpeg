from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SceneType = Literal[
    "title", "concept", "cards", "bars", "steps", "list", "stat", "flow", "compare", "callout", "diagram", "outro",
]


class Item(BaseModel):
    icon: Optional[str] = None
    label: Optional[str] = None
    value: Optional[str] = None
    caption: Optional[str] = None
    cue: Optional[str] = Field(default=None, description="Short phrase from the narration when this item should appear")


class Connection(BaseModel):
    source: int = Field(alias="from")
    to: int
    label: Optional[str] = None
    cue: Optional[str] = None

    model_config = {"populate_by_name": True}


class Scene(BaseModel):
    type: SceneType
    narration: str
    heading: Optional[str] = None
    subheading: Optional[str] = None
    items: list[Item] = []
    connections: list[Connection] = []
    svg: Optional[str] = None  # diagram scenes only: inline SVG fragment


class Storyboard(BaseModel):
    title: str
    theme: str = "ocean"
    scenes: list[Scene]


class CreateProject(BaseModel):
    mode: Literal["prompt", "script"] = "prompt"
    prompt: str = Field(default="", max_length=20000)          # topic/content (prompt mode) or visual instructions (script mode)
    script: Optional[str] = Field(default=None, max_length=20000)  # narrated exactly as written (script mode)
    duration: Literal[30, 60, 300] = 60
    voice_id: Optional[str] = None
    theme: str = "auto"
    captions: bool = False
    language: str = "English"
    hd: bool = False
    hand: bool = False  # show a drawing hand that traces strokes and places elements

    def text_for_title(self) -> str:
        return (self.script or self.prompt or "").strip()
