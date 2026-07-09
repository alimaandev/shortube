from __future__ import annotations

import logging
import re
from typing import Any

from shortube.core.types import Scene, Script
from shortube.shared.llm import LLMProvider
from shortube.shared.logging import get_logger

_VISUAL_DESC_SYSTEM = """You are a visual director for YouTube Shorts.
Given a script segment, describe what should appear on screen.
Be specific and visual — describe scenes, actions, text overlays.
Return JSON: {"visual_description": "string"}
Output valid JSON only — no markdown, no code fences."""

logger = logging.getLogger(__name__)


class SceneSplitter:
    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm

    def split(self, script: Script, total_duration: float) -> list[Scene]:
        sentences = self._split_sentences(script.full_text)
        groups = self._group_sentences(sentences, script)
        scenes = self._build_scenes(groups, script, total_duration)
        self._enrich_visuals(scenes)
        return scenes

    def _split_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p.strip() for p in parts if p.strip()]

    def _group_sentences(
        self, sentences: list[str], script: Script
    ) -> list[list[str]]:
        hook_words = set(script.hook.lower().split()[:5])
        cta_words = set(script.cta.lower().split()[:5])

        hook_group: list[str] = []
        cta_group: list[str] = []
        middle: list[str] = []

        for s in sentences:
            words = set(s.lower().split())
            if hook_group or words & hook_words:
                hook_group.append(s)
            elif cta_group or words & cta_words or s == script.cta:
                cta_group.append(s)
            else:
                middle.append(s)

        # Fallback: if hook/cta not found by word match, use position
        if not hook_group and sentences:
            hook_group = [sentences[0]]
            middle = sentences[1:]
        if not cta_group and middle:
            cta_group = [middle.pop()]
        if not cta_group and not middle:
            cta_group = ["Thanks for watching!"]

        # Distribute middle sentences evenly across 3 points
        n_points = min(3, max(1, len(script.points)))
        if not middle:
            middle = [""] * n_points

        groups = [hook_group]
        chunk_size = max(1, len(middle) // n_points)
        for i in range(n_points):
            start = i * chunk_size
            end = None if i == n_points - 1 else start + chunk_size
            groups.append(middle[start:end])
        groups.append(cta_group)

        return groups

    def _build_scenes(
        self,
        groups: list[list[str]],
        script: Script,
        total_duration: float,
    ) -> list[Scene]:
        scenes: list[Scene] = []

        word_counts = [sum(len(s.split()) for s in g) for g in groups]
        total_words = max(sum(word_counts), 1)

        hook_bonus = 1.2
        adjusted = []
        for i, wc in enumerate(word_counts):
            weight = wc / total_words
            if i == 0:
                weight *= hook_bonus
            adjusted.append(weight)

        adj_total = sum(adjusted)
        durations = [total_duration * (w / adj_total) for w in adjusted]
        min_dur = 1.5
        durations = [max(d, min_dur) for d in durations]

        dur_total = sum(durations)
        if dur_total > total_duration:
            scale = total_duration / dur_total
            durations = [d * scale for d in durations]

        current_time = 0.0
        for i, group in enumerate(groups):
            duration = durations[i] if i < len(durations) else 2.0
            narration = " ".join(group)
            scenes.append(
                Scene(
                    index=i,
                    start_time=current_time,
                    end_time=current_time + duration,
                    narration=narration,
                    visual_description="",
                    transition="fade" if i > 0 else "fade",
                )
            )
            current_time += duration

        return scenes

    def _enrich_visuals(self, scenes: list[Scene]) -> None:
        if self._llm is None:
            for scene in scenes:
                scene.visual_description = scene.narration[:100]
            return

        for scene in scenes:
            if not scene.narration:
                scene.visual_description = ""
                continue
            try:
                result = self._llm.generate_json(
                    _VISUAL_DESC_SYSTEM,
                    f"Script segment: {scene.narration}",
                    temperature=0.5,
                    max_tokens=256,
                )
                scene.visual_description = result.get("visual_description", scene.narration[:100])
            except Exception as e:
                logger.warning("Visual description failed: %s", e)
                scene.visual_description = scene.narration[:100]
