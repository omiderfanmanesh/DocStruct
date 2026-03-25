"""Unit tests for circuit breaker pattern."""

import time

import pytest

from docstruct.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState,
    get_circuit_breaker,
    reset_all_breakers,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_all_breakers()
    yield
    reset_all_breakers()


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_successful_call(self):
        cb = CircuitBreaker("test")
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=10.0)
        cb = CircuitBreaker("test", config=config)

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        cb = CircuitBreaker("test", config=config)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            cb.call(lambda: 42)
        assert "open" in str(exc_info.value).lower()

    def test_transitions_to_half_open_after_timeout(self):
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        cb = CircuitBreaker("test", config=config)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_on_success(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.05,
            success_threshold=1,
        )
        cb = CircuitBreaker("test", config=config)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        time.sleep(0.1)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self):
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.05)
        cb = CircuitBreaker("test", config=config)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        time.sleep(0.1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail again")))

        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config=config)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=config)

        # 2 failures
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        # 1 success resets the count
        cb.call(lambda: "ok")

        # 2 more failures should not trip it
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerRegistry:
    def test_get_creates_new(self):
        cb = get_circuit_breaker("test-new")
        assert cb.name == "test-new"

    def test_get_returns_same_instance(self):
        cb1 = get_circuit_breaker("shared")
        cb2 = get_circuit_breaker("shared")
        assert cb1 is cb2

    def test_reset_all(self):
        cb = get_circuit_breaker("resettable")
        config = CircuitBreakerConfig(failure_threshold=1)
        cb.config = config

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.state == CircuitState.OPEN
        reset_all_breakers()
        assert cb.state == CircuitState.CLOSED
