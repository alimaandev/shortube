from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ── Script ─────────────────────────────────────────────────────────────

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

    @classmethod
    def from_legacy_dict(cls, data: dict) -> Script:
        return cls(
            topic=data.get("topic", ""),
            hook=data.get("hook", ""),
            points=data.get("points", []),
            cta=data.get("cta", ""),
            full_text=data.get("full_text", ""),
            keywords=data.get("keywords", []),
            title=data.get("title", ""),
            tags=data.get("tags", []),
        )

    def to_legacy_dict(self) -> dict:
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


# ── Media ──────────────────────────────────────────────────────────────

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


# ── Scene & Storyboard ─────────────────────────────────────────────────

@dataclass
class Scene:
    index: int
    start_time: float
    end_time: float
    narration: str
    visual_description: str
    search_queries: list[str] = field(default_factory=list)
    selected_media: list[MediaAsset] = field(default_factory=list)
    transition: str = "fade"
    image_fallback: str | None = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class Storyboard:
    script: Script
    scenes: list[Scene] = field(default_factory=list)
    total_duration: float = 0.0


# ── Trend Discovery ────────────────────────────────────────────────────

@dataclass
class TrendIdea:
    title: str
    source: str
    score: float = 0.0
    category: str = ""
    momentum: Literal["rising", "stable", "declining"] = "stable"
    url: str | None = None
    reason: str = ""


# ── Research ───────────────────────────────────────────────────────────

@dataclass
class Fact:
    statement: str
    source: str
    confidence: float = 0.5
    url: str | None = None


@dataclass
class Conflict:
    fact_a: Fact
    fact_b: Fact
    description: str = ""


@dataclass
class Source:
    name: str
    url: str
    authority: float = 0.5


@dataclass
class ResearchNote:
    topic: str
    facts: list[Fact] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    summary: str = ""
