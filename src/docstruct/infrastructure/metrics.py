"""Metrics collection for the search agent pipeline."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageMetric:
    """Accumulated metrics for a single pipeline stage."""

    call_count: int = 0
    total_duration_ms: float = 0.0
    error_count: int = 0
    last_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.call_count if self.call_count > 0 else 0.0

    @property
    def error_rate(self) -> float:
        return self.error_count / self.call_count if self.call_count > 0 else 0.0

    def record(self, duration_ms: float, *, error: bool = False) -> None:
        self.call_count += 1
        self.total_duration_ms += duration_ms
        self.last_duration_ms = duration_ms
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        if error:
            self.error_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_count": self.call_count,
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "min_duration_ms": round(self.min_duration_ms, 1) if self.min_duration_ms != float("inf") else 0.0,
            "max_duration_ms": round(self.max_duration_ms, 1),
            "last_duration_ms": round(self.last_duration_ms, 1),
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 3),
        }


@dataclass
class RetrievalMetrics:
    """Metrics specific to retrieval operations."""

    graph_hits: int = 0
    fulltext_hits: int = 0
    vector_hits: int = 0
    zero_result_queries: int = 0
    total_queries: int = 0
    avg_candidates_per_query: float = 0.0
    _total_candidates: int = field(default=0, init=False, repr=False)

    def record_query(self, *, graph_count: int = 0, fulltext_count: int = 0,
                     vector_count: int = 0, total_candidates: int = 0) -> None:
        self.total_queries += 1
        self.graph_hits += min(graph_count, 1)
        self.fulltext_hits += min(fulltext_count, 1)
        self.vector_hits += min(vector_count, 1)
        self._total_candidates += total_candidates
        self.avg_candidates_per_query = self._total_candidates / self.total_queries
        if total_candidates == 0:
            self.zero_result_queries += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "graph_hit_rate": round(self.graph_hits / max(self.total_queries, 1), 3),
            "fulltext_hit_rate": round(self.fulltext_hits / max(self.total_queries, 1), 3),
            "vector_hit_rate": round(self.vector_hits / max(self.total_queries, 1), 3),
            "zero_result_rate": round(self.zero_result_queries / max(self.total_queries, 1), 3),
            "avg_candidates_per_query": round(self.avg_candidates_per_query, 1),
        }


class MetricsCollector:
    """Thread-safe metrics collector for the search pipeline.

    Collects per-stage timing, retrieval stats, LLM token usage, and quality metrics.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stages: dict[str, StageMetric] = defaultdict(StageMetric)
        self._retrieval = RetrievalMetrics()
        self._llm_calls: int = 0
        self._total_queries: int = 0
        self._clarification_count: int = 0
        self._confidence_scores: list[float] = []
        self._quality_warnings: int = 0

    def record_stage(self, stage: str, duration_ms: float, *, error: bool = False) -> None:
        """Record timing for a pipeline stage."""
        with self._lock:
            self._stages[stage].record(duration_ms, error=error)

    def record_retrieval(self, **kwargs: int) -> None:
        """Record retrieval mode results."""
        with self._lock:
            self._retrieval.record_query(**kwargs)

    def record_llm_call(self) -> None:
        """Increment LLM call counter."""
        with self._lock:
            self._llm_calls += 1

    def record_query(self) -> None:
        """Increment total query counter."""
        with self._lock:
            self._total_queries += 1

    def record_clarification(self) -> None:
        """Increment clarification counter."""
        with self._lock:
            self._clarification_count += 1

    def record_confidence(self, score: float) -> None:
        """Record a confidence score."""
        with self._lock:
            self._confidence_scores.append(score)

    def record_quality_warning(self) -> None:
        """Increment quality warning counter."""
        with self._lock:
            self._quality_warnings += 1

    def get_summary(self) -> dict[str, Any]:
        """Get a full metrics summary."""
        with self._lock:
            avg_confidence = (
                sum(self._confidence_scores) / len(self._confidence_scores)
                if self._confidence_scores
                else 0.0
            )
            return {
                "total_queries": self._total_queries,
                "total_llm_calls": self._llm_calls,
                "clarification_rate": round(
                    self._clarification_count / max(self._total_queries, 1), 3
                ),
                "avg_confidence_score": round(avg_confidence, 3),
                "quality_warnings": self._quality_warnings,
                "stages": {
                    name: metric.to_dict()
                    for name, metric in sorted(self._stages.items())
                },
                "retrieval": self._retrieval.to_dict(),
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._stages.clear()
            self._retrieval = RetrievalMetrics()
            self._llm_calls = 0
            self._total_queries = 0
            self._clarification_count = 0
            self._confidence_scores.clear()
            self._quality_warnings = 0


class Timer:
    """Simple timer for measuring stage durations."""

    def __init__(self) -> None:
        self._start: float = 0.0
        self._end: float = 0.0

    def start(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def stop(self) -> float:
        self._end = time.perf_counter()
        return self.elapsed_ms

    @property
    def elapsed_ms(self) -> float:
        end = self._end if self._end > 0 else time.perf_counter()
        return (end - self._start) * 1000


# Global metrics instance
_global_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return _global_metrics


def reset_metrics() -> None:
    """Reset the global metrics collector."""
    _global_metrics.reset()


def estimate_tokens(input_chars: int, output_chars: int) -> int:
    """Estimate token count from character counts.

    Rough estimate: 1 token ≈ 4 characters for English text.
    Includes overhead multiplier for JSON, tool calls, etc.

    Args:
        input_chars: Characters in input (question, context)
        output_chars: Characters in output (answer, citations)

    Returns:
        Estimated token count
    """
    overhead_multiplier = 1.2
    return int((input_chars + output_chars) / 4 * overhead_multiplier)


def calculate_cost(tokens_used: int) -> float:
    """Calculate approximate cost in USD using Claude Haiku pricing.

    Claude Haiku pricing (as of March 2025):
    - Input: $0.80 per million tokens
    - Output: $4.00 per million tokens

    Assumes 70% input, 30% output split.

    Args:
        tokens_used: Total estimated tokens

    Returns:
        Approximate cost in USD
    """
    INPUT_TOKENS_PER_MILLION = 0.80
    OUTPUT_TOKENS_PER_MILLION = 4.00

    input_tokens = int(tokens_used * 0.7)
    output_tokens = tokens_used - input_tokens

    input_cost = (input_tokens / 1_000_000) * INPUT_TOKENS_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * OUTPUT_TOKENS_PER_MILLION

    return input_cost + output_cost
