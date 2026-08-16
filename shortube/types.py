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
    thumbnail: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "type": self.type,
            "provider": self.provider,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "local_path": self.local_path,
            "thumbnail": self.thumbnail,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MediaAsset:
        return cls(
            url=data.get("url", ""),
            type=data.get("type", "image"),
            provider=data.get("provider", "unknown"),
            width=int(data.get("width", 1080)),
            height=int(data.get("height", 1920)),
            duration=data.get("duration"),
            local_path=data.get("local_path"),
            thumbnail=data.get("thumbnail", ""),
        )


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

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "narration": self.narration,
            "visual_description": self.visual_description,
            "search_queries": self.search_queries,
            "selected_media": [m.to_dict() for m in self.selected_media],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Scene:
        return cls(
            index=int(data.get("index", 0)),
            start_time=float(data.get("start_time", 0.0)),
            end_time=float(data.get("end_time", 0.0)),
            narration=data.get("narration", ""),
            visual_description=data.get("visual_description", ""),
            search_queries=list(data.get("search_queries", [])),
            selected_media=[
                MediaAsset.from_dict(m) for m in data.get("selected_media", [])
            ],
        )


@dataclass
class Storyboard:
    script: Script
    scenes: list[Scene] = field(default_factory=list)
    total_duration: float = 0.0

    def to_dict(self) -> dict:
        return {
            "script": self.script.to_dict(),
            "scenes": [s.to_dict() for s in self.scenes],
            "total_duration": self.total_duration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Storyboard:
        return cls(
            script=Script.from_dict(data.get("script", {})),
            scenes=[Scene.from_dict(s) for s in data.get("scenes", [])],
            total_duration=float(data.get("total_duration", 0.0)),
        )


@dataclass
class TrendIdea:
    title: str
    source: str
    score: float = 0.0
    url: str | None = None
    reason: str = ""
