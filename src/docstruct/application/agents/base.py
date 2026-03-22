"""Shared agent abstractions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any
from abc import ABC, abstractmethod


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    output: Any = None
    error: str | None = None
    warnings: list[str] | None = None
    execution_time_ms: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __str__(self) -> str:
        if self.success:
            duration = self.execution_time_ms or 0.0
            return f"{self.agent_name}: SUCCESS ({duration:.1f}ms)"
        return f"{self.agent_name}: FAILED - {self.error}"


class BaseAgent(ABC):
    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"docstruct.application.agents.{self.name}")
        self._execution_count = 0
        self._total_execution_time = 0.0
        self._last_result: AgentResult | None = None

    @abstractmethod
    async def run(self, input_data: Any) -> AgentResult:
        ...

    def run_sync(self, input_data: Any) -> AgentResult:
        return asyncio.run(self.run(input_data))

    def _log_execution(self, result: AgentResult) -> None:
        self._execution_count += 1
        self._last_result = result
        if result.execution_time_ms:
            self._total_execution_time += result.execution_time_ms
        if result.success:
            self.logger.info("Execution #%s completed in %.1fms", self._execution_count, result.execution_time_ms or 0.0)
        else:
            self.logger.error("Execution #%s failed: %s", self._execution_count, result.error)
        for warning in result.warnings or []:
            self.logger.warning("  %s", warning)

    def get_stats(self) -> dict[str, Any]:
        avg_time = self._total_execution_time / self._execution_count if self._execution_count else 0.0
        return {
            "agent_name": self.name,
            "execution_count": self._execution_count,
            "total_execution_time_ms": self._total_execution_time,
            "average_execution_time_ms": avg_time,
            "last_result": self._last_result,
        }


class AgentChain:
    def __init__(self, name: str = "AgentChain"):
        self.name = name
        self.agents: list[BaseAgent] = []
        self.logger = logging.getLogger(f"docstruct.application.agents.{name}")
        self._stop_on_failure = True

    def add_agent(self, agent: BaseAgent) -> "AgentChain":
        self.agents.append(agent)
        return self

    def stop_on_failure(self, stop: bool = True) -> "AgentChain":
        self._stop_on_failure = stop
        return self

    async def run(self, initial_input: Any) -> dict[str, AgentResult]:
        results: dict[str, AgentResult] = {}
        current_input = initial_input
        for agent in self.agents:
            self.logger.debug("Running agent: %s", agent.name)
            result = await agent.run(current_input)
            results[agent.name] = result
            if not result.success and self._stop_on_failure:
                self.logger.error("Chain halted: %s failed", agent.name)
                break
            current_input = result.output
        return results

