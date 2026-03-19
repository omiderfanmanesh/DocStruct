"""
Unified base agent class for docstruct.

Provides async ABC pattern for all agents (TOC extraction, JSON parsing, etc.)
with support for both async/await and sync-wrapper convenience methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
import logging
from datetime import datetime
import asyncio


logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from agent execution."""
    
    agent_name: str
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    warnings: Optional[List[str]] = None
    execution_time_ms: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __str__(self):
        if self.success:
            return f"{self.agent_name}: SUCCESS ({self.execution_time_ms:.1f}ms)"
        else:
            return f"{self.agent_name}: FAILED - {self.error}"


class BaseAgent(ABC):
    """
    Abstract base class for all docstruct agents.
    
    Agents are responsible for specific processing tasks in pipelines.
    Each agent:
    - Accepts structured input
    - Processes it independently
    - Returns AgentResult with output or error
    
    Subclasses must implement the async run() method.
    """
    
    def __init__(self, name: Optional[str] = None):
        """
        Initialize agent.
        
        Args:
            name: Optional custom agent name (defaults to class name)
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"docstruct.agents.{self.name}")
        self._execution_count = 0
        self._total_execution_time = 0.0
        self._last_result: Optional[AgentResult] = None
    
    @abstractmethod
    async def run(self, input_data: Any) -> AgentResult:
        """
        Process input and return result (async).
        
        Subclasses must implement this method.
        
        Args:
            input_data: Input data to process
            
        Returns:
            AgentResult with success status and output or error
        """
        pass
    
    def run_sync(self, input_data: Any) -> AgentResult:
        """
        Convenience method to run agent synchronously.
        
        Wraps async run() for code that can't use await.
        
        Args:
            input_data: Input data to process
            
        Returns:
            AgentResult with success status and output or error
        """
        return asyncio.run(self.run(input_data))
    
    def _log_execution(self, result: AgentResult):
        """Log and track execution metrics."""
        self._execution_count += 1
        self._last_result = result
        
        if result.execution_time_ms:
            self._total_execution_time += result.execution_time_ms
        
        if result.success:
            self.logger.info(
                f"Execution #{self._execution_count} completed in "
                f"{result.execution_time_ms:.1f}ms"
            )
        else:
            self.logger.error(
                f"Execution #{self._execution_count} failed: {result.error}"
            )
        
        if result.warnings:
            for warning in result.warnings:
                self.logger.warning(f"  {warning}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent execution statistics."""
        avg_time = (
            self._total_execution_time / self._execution_count
            if self._execution_count > 0
            else 0.0
        )
        
        return {
            "agent_name": self.name,
            "execution_count": self._execution_count,
            "total_execution_time_ms": self._total_execution_time,
            "average_execution_time_ms": avg_time,
            "last_result": self._last_result,
        }


class AgentChain:
    """
    Chain multiple agents for sequential processing.
    
    Each agent's output becomes the next agent's input.
    Stops on first failure unless configured otherwise.
    
    Example:
        chain = (AgentChain("MyPipeline")
                 .add_agent(BoundaryAgent())
                 .add_agent(ClassifierAgent())
                 .add_agent(MetadataAgent()))
        results = await chain.run(toc_text)
    """
    
    def __init__(self, name: str = "AgentChain"):
        """Initialize chain."""
        self.name = name
        self.agents: List[BaseAgent] = []
        self.logger = logging.getLogger(f"docstruct.{name}")
        self._stop_on_failure = True
    
    def add_agent(self, agent: BaseAgent) -> "AgentChain":
        """
        Add agent to chain.
        
        Args:
            agent: Agent to add
            
        Returns:
            Self for chaining
        """
        self.agents.append(agent)
        return self
    
    def stop_on_failure(self, stop: bool = True) -> "AgentChain":
        """
        Configure whether to stop on agent failure.
        
        Args:
            stop: True to stop on failure (default), False to continue
            
        Returns:
            Self for chaining
        """
        self._stop_on_failure = stop
        return self
    
    async def run(self, initial_input: Any) -> Dict[str, AgentResult]:
        """
        Run all agents in sequence.
        
        Args:
            initial_input: Initial input for first agent
            
        Returns:
            Dict mapping agent names to their results
        """
        results = {}
        current_input = initial_input
        
        for agent in self.agents:
            self.logger.debug(f"Running agent: {agent.name}")
            result = await agent.run(current_input)
            results[agent.name] = result
            
            if not result.success:
                self.logger.error(f"Chain halted: {agent.name} failed")
                if self._stop_on_failure:
                    break
            
            current_input = result.output
        
        return results


__all__ = [
    "BaseAgent",
    "AgentResult",
    "AgentChain",
]
