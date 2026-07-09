from __future__ import annotations

import logging
from typing import Sequence

from shortube.core.exceptions import ResearchError
from shortube.core.interfaces import ResearchEngine as ResearchEngineInterface
from shortube.core.types import Fact, ResearchNote, Source
from shortube.research.deduplicator import deduplicate_facts
from shortube.research.fact_checker import FactChecker
from shortube.research.sources import LLMKnowledgeSource, WikipediaSource
from shortube.shared.llm import LLMProvider
from shortube.shared.logging import get_logger

_SUMMARY_SYSTEM_PROMPT = """Summarize the following research facts into a coherent paragraph.
Focus on the most important and well-supported information.
Keep it concise (2-4 sentences)."""


class ResearchEngine(ResearchEngineInterface):
    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm
        self._logger = get_logger("research")
        self._sources: list = []

        # Register built-in sources
        self.add_source(WikipediaSource())
        if llm is not None:
            self.add_source(LLMKnowledgeSource(llm))

        self._fact_checker = FactChecker(llm)

    def add_source(self, source) -> ResearchEngine:
        self._sources.append(source)
        return self

    def research(self, topic: str) -> ResearchNote:
        self._logger.info("Researching topic: %s", topic)

        all_facts: list[Fact] = []
        all_sources: list[Source] = []

        for source in self._sources:
            try:
                self._logger.debug("Fetching from source: %s", source.name)
                facts = source.fetch(topic)
                self._logger.debug("Got %d facts from %s", len(facts), source.name)
                all_facts.extend(facts)
            except Exception as e:
                self._logger.warning("Source '%s' failed: %s", source.name, e)

        if not all_facts:
            return ResearchNote(
                topic=topic,
                facts=[],
                conflicts=[],
                sources=[],
                summary=f"No research data found for: {topic}",
            )

        # Deduplicate
        unique_facts = deduplicate_facts(all_facts)

        # Check for conflicts
        conflicts = self._fact_checker.check_conflicts(unique_facts)

        # Build source list
        seen_urls: set[str] = set()
        for fact in unique_facts:
            url = fact.url or ""
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_sources.append(
                    Source(
                        name=fact.source.split(":")[0].strip(),
                        url=url,
                        authority=0.7 if "wikipedia" in fact.source.lower() else 0.5,
                    )
                )

        # Generate summary (LLM or fallback)
        summary = self._generate_summary(unique_facts)

        return ResearchNote(
            topic=topic,
            facts=unique_facts,
            conflicts=conflicts,
            sources=all_sources,
            summary=summary,
        )

    def _generate_summary(self, facts: Sequence[Fact]) -> str:
        if not facts:
            return ""
        if self._llm is None:
            return " ".join(f.statement for f in facts[:3])
        facts_text = "\n".join(f"- {f.statement}" for f in facts[:10])
        try:
            return self._llm.generate(
                _SUMMARY_SYSTEM_PROMPT, facts_text,
                temperature=0.3, max_tokens=256,
            )
        except Exception as e:
            self._logger.warning("Summary generation failed: %s", e)
            return " ".join(f.statement for f in facts[:3])
