from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from shortube.core.types import MediaAsset, ResearchNote, Script, Storyboard, TrendIdea


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str: ...


class Agent(ABC):
    @abstractmethod
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class DiscoverySource(ABC):
    @abstractmethod
    def fetch(self, **kwargs) -> list[TrendIdea]:
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class MediaProvider(ABC):
    @abstractmethod
    def search(
        self,
        query: str,
        media_type: str = "video",
        orientation: str = "portrait",
        max_results: int = 10,
    ) -> list[MediaAsset]: ...


class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> Any | None: ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    @abstractmethod
    def invalidate(self, key: str) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


# ── Pipeline stage interfaces ──────────────────────────────────────────

class ScriptWriter(ABC):
    @abstractmethod
    def write_script(self, topic: str) -> Script: ...


class VoiceGenerator(ABC):
    @abstractmethod
    def generate(self, text: str, output_path: str) -> str: ...


class StoryboardGenerator(ABC):
    @abstractmethod
    def generate(self, script: Script, voiceover_path: str) -> Storyboard: ...


class VideoAssembler(ABC):
    @abstractmethod
    def assemble(
        self,
        storyboard: Storyboard,
        voiceover_path: str,
        output_path: str,
    ) -> str: ...


class VideoUploader(ABC):
    @abstractmethod
    def upload(
        self,
        video_path: str,
        script: Script,
        privacy: str = "private",
        channel_id: str | None = None,
    ) -> str: ...


class ResearchEngine(ABC):
    @abstractmethod
    def research(self, topic: str) -> ResearchNote: ...
