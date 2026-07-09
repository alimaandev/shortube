from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from shortube.core.interfaces import Agent, LLMProvider
from shortube.shared.logging import get_logger


class BaseAgent(Agent, ABC):
    def __init__(self, llm: LLMProvider, config: dict[str, Any] | None = None):
        self._llm = llm
        self._config = config or {}
        self._logger: logging.Logger = get_logger(f"agent.{self.name}")

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> dict[str, Any]: ...

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        self._logger.debug("LLM call — system=%d chars, user=%d chars",
                           len(system_prompt), len(user_prompt))
        return self._llm.generate_json(system_prompt, user_prompt, temperature, max_tokens)
