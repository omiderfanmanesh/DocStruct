"""Response metrics tracking for Claude Code sessions.

Tracks and reports execution time, estimated token usage, and approximate cost
for transparency and cost management.
"""

import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class ResponseMetrics:
    """Metrics for a Claude Code response."""

    start_time: float
    end_time: Optional[float] = None
    tokens_used: int = 0
    token_cost: float = 0.0  # in USD

    @property
    def execution_time_seconds(self) -> float:
        """Get execution time in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time

    def complete(self) -> None:
        """Mark metrics as complete."""
        self.end_time = time.time()

    def format_summary(self) -> str:
        """Format metrics as a summary string."""
        self.complete()
        return (
            f"\n**Metrics:**\n"
            f"- Execution time: {self.execution_time_seconds:.2f}s\n"
            f"- Tokens used: ~{self.tokens_used:,}\n"
            f"- Estimated cost: ${self.token_cost:.4f}"
        )


class MetricsTracker:
    """Track metrics for the current session."""

    # Claude Haiku 4.5 pricing (as of March 2025)
    INPUT_TOKENS_PER_MILLION = 0.80  # $0.80 per million input tokens
    OUTPUT_TOKENS_PER_MILLION = 4.00  # $4.00 per million output tokens

    def __init__(self):
        self.metrics: Optional[ResponseMetrics] = None

    def start(self) -> ResponseMetrics:
        """Start tracking a new response."""
        self.metrics = ResponseMetrics(start_time=time.time())
        return self.metrics

    def estimate_tokens(self, input_chars: int, output_chars: int) -> int:
        """Estimate tokens from character counts.

        Rough estimate: 1 token ≈ 4 characters for English text.
        """
        # Account for tool calls and JSON overhead
        overhead_multiplier = 1.2
        return int((input_chars + output_chars) / 4 * overhead_multiplier)

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate approximate cost in USD."""
        input_cost = (input_tokens / 1_000_000) * self.INPUT_TOKENS_PER_MILLION
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_TOKENS_PER_MILLION
        return input_cost + output_cost

    def update_metrics(self, input_chars: int, output_chars: int) -> None:
        """Update metrics with character estimates."""
        if self.metrics is None:
            self.metrics = ResponseMetrics(start_time=time.time())

        # Split estimated tokens between input/output
        total_tokens = self.estimate_tokens(input_chars, output_chars)
        input_tokens = int(total_tokens * 0.7)  # Assume 70% input, 30% output
        output_tokens = total_tokens - input_tokens

        self.metrics.tokens_used = total_tokens
        self.metrics.token_cost = self.calculate_cost(input_tokens, output_tokens)

    def finish(self) -> ResponseMetrics:
        """Finish tracking and return metrics."""
        if self.metrics is None:
            self.metrics = ResponseMetrics(start_time=time.time())
        self.metrics.complete()
        return self.metrics


# Global tracker instance
_tracker = MetricsTracker()


def start_response_metrics() -> ResponseMetrics:
    """Start tracking metrics for this response."""
    return _tracker.start()


def get_current_metrics() -> Optional[ResponseMetrics]:
    """Get current metrics being tracked."""
    return _tracker.metrics


def format_response_metrics(
    input_chars: int = 0,
    output_chars: int = 0,
) -> str:
    """Format and return response metrics summary.

    Args:
        input_chars: Approximate characters in input
        output_chars: Approximate characters in output

    Returns:
        Formatted metrics string to append to response
    """
    _tracker.update_metrics(input_chars, output_chars)
    metrics = _tracker.finish()
    return metrics.format_summary()


if __name__ == "__main__":
    # Example usage
    tracker = MetricsTracker()
    tracker.start()

    # Simulate some work
    time.sleep(0.5)

    # Update with estimates
    tracker.update_metrics(input_chars=5000, output_chars=2000)
    metrics = tracker.finish()

    print(metrics.format_summary())
