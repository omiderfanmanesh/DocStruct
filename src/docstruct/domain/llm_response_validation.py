"""LLM response validation with per-field fallbacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResponseValidation:
    """Result of validating an LLM response against its expected Pydantic schema."""

    is_valid: bool
    """True if all required fields are present and correctly typed."""

    missing_fields: list[str] = field(default_factory=list)
    """Names of fields that were None or absent from the response."""

    type_mismatches: dict[str, str] = field(default_factory=dict)
    """Field name → description of type mismatch (e.g., 'str instead of list')."""

    fallbacks_applied: dict[str, str] = field(default_factory=dict)
    """Field name → fallback strategy that was applied (e.g., 'use original question')."""

    degraded: bool = False
    """True if any fallback was applied; indicates response quality is reduced."""


def validate_llm_response(
    payload: T,
    required_fields: dict[str, type],
    fallback_strategies: dict[str, Callable[[], Any]] | None = None,
) -> tuple[T, LLMResponseValidation]:
    """Validate an LLM response against expected schema and apply per-field fallbacks.

    Never raises an exception — always returns a result. If validation fails, fallbacks
    are applied and the degraded flag is set to True.

    Args:
        payload: The LLM response object to validate (Pydantic BaseModel instance)
        required_fields: Dict of {field_name: expected_type} for required fields
        fallback_strategies: Dict of {field_name: callable_returning_fallback_value} for per-field fallbacks

    Returns:
        Tuple of (potentially modified payload, LLMResponseValidation result)
        - payload: May have fields replaced with fallback values
        - validation: Result object including missing_fields, type_mismatches, fallbacks_applied, degraded flag
    """
    if fallback_strategies is None:
        fallback_strategies = {}

    missing_fields: list[str] = []
    type_mismatches: dict[str, str] = {}
    fallbacks_applied: dict[str, str] = {}
    degraded = False

    # Check each required field
    for field_name, expected_type in required_fields.items():
        if not hasattr(payload, field_name):
            missing_fields.append(field_name)
            degraded = True
            # Apply fallback if available
            if field_name in fallback_strategies:
                try:
                    fallback_value = fallback_strategies[field_name]()
                    setattr(payload, field_name, fallback_value)
                    fallbacks_applied[field_name] = f"fallback_strategies[{field_name}]"
                except Exception:
                    # If fallback fails, just note the missing field
                    pass
        else:
            field_value = getattr(payload, field_name)
            # Check if None or type mismatch
            if field_value is None:
                missing_fields.append(field_name)
                degraded = True
                if field_name in fallback_strategies:
                    try:
                        fallback_value = fallback_strategies[field_name]()
                        setattr(payload, field_name, fallback_value)
                        fallbacks_applied[field_name] = f"fallback_strategies[{field_name}]"
                    except Exception:
                        pass
            elif not isinstance(field_value, expected_type):
                # Type mismatch — try to coerce or apply fallback
                type_name = getattr(expected_type, "__name__", str(expected_type))
                actual_type = getattr(type(field_value), "__name__", str(type(field_value)))
                type_mismatches[field_name] = f"expected {type_name}, got {actual_type}"
                degraded = True
                if field_name in fallback_strategies:
                    try:
                        fallback_value = fallback_strategies[field_name]()
                        setattr(payload, field_name, fallback_value)
                        fallbacks_applied[field_name] = f"type_coercion_fallback"
                    except Exception:
                        pass

    is_valid = len(missing_fields) == 0 and len(type_mismatches) == 0

    return payload, LLMResponseValidation(
        is_valid=is_valid,
        missing_fields=missing_fields,
        type_mismatches=type_mismatches,
        fallbacks_applied=fallbacks_applied,
        degraded=degraded,
    )
