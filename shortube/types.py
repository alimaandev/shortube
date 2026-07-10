from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Script:
    topic: str
    hook: str
    points: list[str]
    cta: str
    full_text: str
    keywords: list[str] = field(default_factory=list)
    title: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "hook": self.hook,
            "points": self.points,
            "cta": self.cta,
            "full_text": self.full_text,
            "keywords": self.keywords,
            "title": self.title,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Script:
        _strip = lambda t: re.sub(r"<[^>]+>", "", t).strip()
        return cls(
            topic=_strip(data.get("topic", "")),
            hook=_strip(data.get("hook", "")),
            points=[_strip(p) for p in data.get("points", [])],
            cta=_strip(data.get("cta", "")),
            full_text=_strip(data.get("full_text", "")),
            keywords=data.get("keywords", []),
            title=_strip(data.get("title", "")),
            tags=data.get("tags", []),
        )


MediaType = Literal["video", "image"]


@dataclass
class MediaAsset:
    url: str
    type: MediaType
    provider: str
    width: int
    height: int
    duration: float | None = None
    local_path: str | None = None


@dataclass
class Scene:
    index: int
    start_time: float
    end_time: float
    narration: str
    visual_description: str
    search_queries: list[str] = field(default_factory=list)
    selected_media: list[MediaAsset] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class Storyboard:
    script: Script
    scenes: list[Scene] = field(default_factory=list)
    total_duration: float = 0.0


@dataclass
class TrendIdea:
    title: str
    source: str
    score: float = 0.0
    url: str | None = None
    reason: str = ""
