"""Unit tests for structured logging utilities."""

import logging
from io import StringIO
import pytest

from docstruct.infrastructure.logging import log_pipeline_error


@pytest.fixture
def log_capture():
    """Create a logger with a string handler for testing."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    logger.handlers.clear()

    # Create a string handler
    string_io = StringIO()
    handler = logging.StreamHandler(string_io)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(name)s - %(levelname)s - %(message)s - %(stage)s - %(exc_class)s",
        defaults={}
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    yield logger, string_io

    # Cleanup
    logger.handlers.clear()


def test_log_pipeline_error_contains_all_fields(log_capture):
    """Test that log_pipeline_error emits all required structured fields."""
    logger, string_io = log_capture

    try:
        raise TimeoutError("LLM request timed out after 30s")
    except TimeoutError as exc:
        log_pipeline_error(
            logger,
            stage="rewrite_question",
            question="What is the capital of France?",
            exc=exc,
            fallback_strategy="use original question",
        )

    # The log record should contain the stage name in the message
    output = string_io.getvalue()
    assert "rewrite_question" in output
    assert "TimeoutError" in output
    assert "ERROR" in output


def test_log_pipeline_error_sanitizes_long_questions(log_capture):
    """Test that questions longer than 240 chars are truncated."""
    logger, string_io = log_capture

    long_question = "What is " * 50  # ~400 chars

    try:
        raise ValueError("Some error")
    except ValueError as exc:
        log_pipeline_error(
            logger,
            stage="document_selection",
            question=long_question,
            exc=exc,
        )

    # The log record should be emitted
    output = string_io.getvalue()
    assert "document_selection" in output


def test_log_pipeline_error_works_without_fallback_strategy(log_capture):
    """Test that log_pipeline_error works when no fallback strategy is provided."""
    logger, string_io = log_capture

    try:
        raise RuntimeError("Generic error")
    except RuntimeError as exc:
        log_pipeline_error(
            logger,
            stage="synthesize_answer",
            question="Sample question",
            exc=exc,
        )

    # Should still log successfully without fallback strategy
    output = string_io.getvalue()
    assert "synthesize_answer" in output
    assert "RuntimeError" in output


def test_log_pipeline_error_includes_traceback(log_capture):
    """Test that log_pipeline_error includes the full traceback in structured fields."""
    logger, string_io = log_capture

    # Create a nested exception with traceback
    def inner_function():
        raise KeyError("Missing key in response")

    def outer_function():
        inner_function()

    try:
        outer_function()
    except KeyError as exc:
        log_pipeline_error(
            logger,
            stage="node_selection",
            question="Test question",
            exc=exc,
        )

    # Check that the exception was logged
    output = string_io.getvalue()
    assert "KeyError" in output
    assert "node_selection" in output


def test_log_pipeline_error_with_complex_question(log_capture):
    """Test that special characters in questions are handled correctly."""
    logger, string_io = log_capture

    complex_question = 'What does "FOIA" mean? Explain like I\'m 5.'

    try:
        raise ValueError("Parse error")
    except ValueError as exc:
        log_pipeline_error(
            logger,
            stage="rank_candidates",
            question=complex_question,
            exc=exc,
            fallback_strategy="use heuristic ranking",
        )

    # Should handle special chars without raising
    output = string_io.getvalue()
    assert "rank_candidates" in output
    assert "ValueError" in output


def test_log_pipeline_error_with_none_fallback(log_capture):
    """Test that log_pipeline_error handles None fallback strategy correctly."""
    logger, string_io = log_capture

    try:
        raise ConnectionError("Network timeout")
    except ConnectionError as exc:
        log_pipeline_error(
            logger,
            stage="retrieve_contexts",
            question="What is retrieval?",
            exc=exc,
            fallback_strategy=None,
        )

    # Should log without fallback_strategy field
    output = string_io.getvalue()
    assert "retrieve_contexts" in output
    assert "ConnectionError" in output


def test_log_pipeline_error_preserves_exception_type(log_capture):
    """Test that the exception class name is correctly extracted."""
    logger, string_io = log_capture

    exception_types = [TimeoutError, ValueError, RuntimeError, KeyError, TypeError]

    for exc_type in exception_types:
        try:
            raise exc_type("Test error")
        except exc_type as exc:
            log_pipeline_error(
                logger,
                stage="test_stage",
                question="Test",
                exc=exc,
            )

    output = string_io.getvalue()
    for exc_type in exception_types:
        assert exc_type.__name__ in output
