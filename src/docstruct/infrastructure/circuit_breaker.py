"""Circuit breaker pattern for external service calls (Neo4j, LLM APIs)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker instance."""

    failure_threshold: int = 5       # Failures before opening
    recovery_timeout: float = 30.0   # Seconds before trying half-open
    half_open_max_calls: int = 1     # Calls allowed in half-open state
    success_threshold: int = 2       # Successes needed to close from half-open


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and rejecting calls."""

    def __init__(self, name: str, seconds_until_retry: float):
        self.name = name
        self.seconds_until_retry = seconds_until_retry
        super().__init__(
            f"Circuit breaker '{name}' is open. "
            f"Retry in {seconds_until_retry:.1f}s."
        )


@dataclass
class CircuitBreaker:
    """Thread-safe circuit breaker for external service calls.

    Usage:
        breaker = CircuitBreaker("neo4j")
        try:
            result = breaker.call(lambda: driver.session().run("MATCH ..."))
        except CircuitBreakerOpen:
            # Use fallback
            result = fallback_result()
    """

    name: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._effective_state()

    def _effective_state(self) -> CircuitState:
        """Determine effective state, considering recovery timeout."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._success_count = 0
        return self._state

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function through the circuit breaker.

        Args:
            func: Function to call.
            *args, **kwargs: Arguments to pass.

        Returns:
            Function return value.

        Raises:
            CircuitBreakerOpen: If circuit is open.
            Exception: If func raises and circuit stays closed.
        """
        with self._lock:
            state = self._effective_state()

            if state == CircuitState.OPEN:
                seconds_left = max(
                    0.0,
                    self.config.recovery_timeout - (time.monotonic() - self._last_failure_time),
                )
                raise CircuitBreakerOpen(self.name, seconds_left)

            if state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpen(self.name, self.config.recovery_timeout)
                self._half_open_calls += 1

        # Execute outside the lock
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self._on_failure(exc)
            raise
        else:
            self._on_success()
            return result

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            else:
                self._failure_count = 0

    def _on_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Manually reset to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0


# Global circuit breaker registry
_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Get or create a named circuit breaker from the global registry."""
    with _registry_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(
                name=name,
                config=config or CircuitBreakerConfig(),
            )
        return _breakers[name]


def reset_all_breakers() -> None:
    """Reset all circuit breakers (useful for testing)."""
    with _registry_lock:
        for breaker in _breakers.values():
            breaker.reset()
