from __future__ import annotations

import logging
from typing import Any

from shortube.core.exceptions import AgentError
from shortube.core.interfaces import Agent
from shortube.shared.logging import get_logger


class AgentPipeline:
    def __init__(self, agents: list[Agent]):
        self.agents = agents
        self._logger: logging.Logger = get_logger("agent_pipeline")

    def run(self, topic: str) -> dict[str, Any]:
        context: dict[str, Any] = {"topic": topic}
        for agent in self.agents:
            self._logger.info("→ Agent: %s", agent.name)
            try:
                context = agent.execute(context)
            except Exception as e:
                raise AgentError(f"Agent '{agent.name}' failed: {e}") from e
        return context

    def add(self, agent: Agent) -> AgentPipeline:
        self.agents.append(agent)
        return self
