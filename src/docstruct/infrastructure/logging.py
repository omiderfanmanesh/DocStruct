"""Structured logging for the search agent pipeline."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

# Module-level logger
logger = logging.getLogger("docstruct.search")


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production observability."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add structured extra fields
        for key in ("stage", "duration_ms", "document_id", "question_preview",
                     "error_type", "error_message", "metric_name", "metric_value",
                     "retrieval_backend", "candidate_count", "context_count",
                     "citation_count", "confidence_score"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value
        if record.exc_info and record.exc_info[1]:
            log_entry["error_type"] = type(record.exc_info[1]).__name__
            log_entry["error_message"] = str(record.exc_info[1])
        return json.dumps(log_entry, default=str)


def configure_logging(*, level: int = logging.INFO, structured: bool = True) -> None:
    """Configure the docstruct search logger.

    Args:
        level: Logging level.
        structured: If True, use JSON-structured output. If False, use standard formatting.
    """
    search_logger = logging.getLogger("docstruct.search")
    search_logger.setLevel(level)

    if not search_logger.handlers:
        handler = logging.StreamHandler()
        if structured:
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
        search_logger.addHandler(handler)


def log_pipeline_error(
    log: logging.Logger,
    stage: str,
    question: str,
    exc: Exception,
    fallback_strategy: str | None = None,
) -> None:
    """Log a pipeline error with structured fields for production observability.

    Sanitizes the question, captures the exception type and traceback, and logs
    the fallback strategy if available.

    Args:
        log: The logger instance to use.
        stage: Pipeline stage name (e.g., "rewrite_question", "document_selection").
        question: The user's question (will be truncated to 240 chars).
        exc: The exception that occurred.
        fallback_strategy: Optional description of the fallback strategy applied.
    """
    # Sanitize question to 240 characters
    sanitized_question = question[:240] if question else ""

    # Build extra fields
    extra: dict[str, Any] = {
        "stage": stage,
        "question_preview": sanitized_question,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    if fallback_strategy:
        extra["fallback_strategy"] = fallback_strategy

    # Log with exception context (includes traceback)
    log.exception(
        "Pipeline error in %s: %s - %s (fallback: %s)",
        stage,
        type(exc).__name__,
        str(exc),
        fallback_strategy or "none",
        extra=extra,
    )


@contextmanager
def log_stage(stage: str, **extra: Any) -> Generator[dict[str, Any], None, None]:
    """Context manager that logs stage entry and exit with duration.

    Usage:
        with log_stage("rewrite_question", question_preview="What...") as ctx:
            result = do_work()
            ctx["result_size"] = len(result)
    """
    context: dict[str, Any] = {}
    start = time.perf_counter()
    logger.info(
        "Stage started: %s",
        stage,
        extra={"stage": stage, **extra},
    )
    try:
        yield context
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Stage completed: %s (%.1fms)",
            stage,
            duration_ms,
            extra={"stage": stage, "duration_ms": round(duration_ms, 1), **extra, **context},
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "Stage failed: %s (%.1fms) - %s: %s",
            stage,
            duration_ms,
            type(exc).__name__,
            exc,
            extra={
                "stage": stage,
                "duration_ms": round(duration_ms, 1),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                **extra,
            },
        )
        raise
