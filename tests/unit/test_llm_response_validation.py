"""Unit tests for LLM response validation with per-field fallbacks."""

from dataclasses import dataclass
import pytest

from docstruct.domain.llm_response_validation import validate_llm_response, LLMResponseValidation


@dataclass
class MockResponse:
    """Mock LLM response for testing."""

    question: str = ""
    answer: str = ""
    document_ids: list[str] | None = None


def test_validate_llm_response_valid_response():
    """Test that a well-formed response is marked as valid."""
    response = MockResponse(question="What is X?", answer="X is Y.", document_ids=["doc1", "doc2"])

    required_fields = {
        "question": str,
        "answer": str,
        "document_ids": list,
    }

    result, validation = validate_llm_response(response, required_fields)

    assert validation.is_valid is True
    assert validation.degraded is False
    assert validation.missing_fields == []
    assert validation.type_mismatches == {}


def test_validate_llm_response_missing_field():
    """Test that missing required fields are detected."""
    response = MockResponse(question="What is X?", answer="X is Y.")

    required_fields = {
        "question": str,
        "answer": str,
        "document_ids": list,
    }

    result, validation = validate_llm_response(response, required_fields)

    assert validation.is_valid is False
    assert validation.degraded is True
    assert "document_ids" in validation.missing_fields


def test_validate_llm_response_none_field():
    """Test that None-valued fields are treated as missing."""
    response = MockResponse(question="What is X?", answer="X is Y.", document_ids=None)

    required_fields = {
        "question": str,
        "answer": str,
        "document_ids": list,
    }

    result, validation = validate_llm_response(response, required_fields)

    assert validation.is_valid is False
    assert validation.degraded is True
    assert "document_ids" in validation.missing_fields


def test_validate_llm_response_type_mismatch():
    """Test that type mismatches are detected."""
    response = MockResponse(question="What is X?", answer="X is Y.", document_ids="doc1,doc2")

    required_fields = {
        "question": str,
        "answer": str,
        "document_ids": list,
    }

    result, validation = validate_llm_response(response, required_fields)

    assert validation.is_valid is False
    assert validation.degraded is True
    assert "document_ids" in validation.type_mismatches
    assert "str" in validation.type_mismatches["document_ids"]


def test_validate_llm_response_with_fallback():
    """Test that fallback strategies are applied."""
    response = MockResponse(question="What is X?", answer=None)

    required_fields = {
        "question": str,
        "answer": str,
    }

    fallback_strategies = {
        "answer": lambda: "Unable to generate answer",
    }

    result, validation = validate_llm_response(response, required_fields, fallback_strategies)

    assert result.answer == "Unable to generate answer"
    assert "answer" in validation.fallbacks_applied
    assert validation.degraded is True


def test_validate_llm_response_multiple_fallbacks():
    """Test that multiple field fallbacks are applied."""
    response = MockResponse(question="What is X?", answer=None, document_ids=None)

    required_fields = {
        "question": str,
        "answer": str,
        "document_ids": list,
    }

    fallback_strategies = {
        "answer": lambda: "Unable to generate answer",
        "document_ids": lambda: ["fallback_doc"],
    }

    result, validation = validate_llm_response(response, required_fields, fallback_strategies)

    assert result.answer == "Unable to generate answer"
    assert result.document_ids == ["fallback_doc"]
    assert len(validation.fallbacks_applied) == 2
    assert validation.degraded is True


def test_validate_llm_response_fallback_failure_silenced():
    """Test that fallback strategy failures are silenced gracefully."""
    response = MockResponse(question="What is X?", answer=None)

    required_fields = {
        "answer": str,
    }

    def failing_fallback():
        raise RuntimeError("Fallback generation failed")

    fallback_strategies = {
        "answer": failing_fallback,
    }

    # Should not raise an exception
    result, validation = validate_llm_response(response, required_fields, fallback_strategies)

    assert validation.degraded is True
    assert "answer" in validation.missing_fields
    # Fallback was not applied because it raised
    assert "answer" not in validation.fallbacks_applied


def test_validate_llm_response_no_fallbacks_provided():
    """Test validation when no fallback strategies are provided."""
    response = MockResponse(question="What is X?", answer=None)

    required_fields = {
        "question": str,
        "answer": str,
    }

    result, validation = validate_llm_response(response, required_fields, fallback_strategies=None)

    assert validation.is_valid is False
    assert validation.degraded is True
    assert "answer" in validation.missing_fields
    assert validation.fallbacks_applied == {}


def test_validate_llm_response_type_coercion_fallback():
    """Test that type mismatch triggers fallback application."""
    response = MockResponse(question="What is X?", answer=123)  # int instead of str

    required_fields = {
        "question": str,
        "answer": str,
    }

    fallback_strategies = {
        "answer": lambda: "Fallback answer for type mismatch",
    }

    result, validation = validate_llm_response(response, required_fields, fallback_strategies)

    assert validation.is_valid is False
    assert validation.degraded is True
    assert "answer" in validation.type_mismatches
    assert result.answer == "Fallback answer for type mismatch"
    assert "answer" in validation.fallbacks_applied


def test_validate_llm_response_empty_required_fields():
    """Test validation with no required fields."""
    response = MockResponse(question="What is X?", answer="X is Y.")

    required_fields = {}

    result, validation = validate_llm_response(response, required_fields)

    assert validation.is_valid is True
    assert validation.degraded is False


def test_validate_llm_response_mixed_valid_and_invalid_fields():
    """Test response with mix of valid and invalid fields."""
    response = MockResponse(question="What is X?", answer=None, document_ids=["doc1"])

    required_fields = {
        "question": str,
        "answer": str,
        "document_ids": list,
    }

    fallback_strategies = {
        "answer": lambda: "Default answer",
    }

    result, validation = validate_llm_response(response, required_fields, fallback_strategies)

    assert validation.is_valid is False
    assert validation.degraded is True
    # question and document_ids are valid
    assert result.question == "What is X?"
    assert result.document_ids == ["doc1"]
    # answer was fallback'd
    assert result.answer == "Default answer"


def test_validation_result_dataclass():
    """Test that LLMResponseValidation dataclass works correctly."""
    validation = LLMResponseValidation(
        is_valid=False,
        missing_fields=["citations"],
        type_mismatches={"document_ids": "expected list, got str"},
        fallbacks_applied={"answer": "fallback_strategies[answer]"},
        degraded=True,
    )

    assert validation.is_valid is False
    assert "citations" in validation.missing_fields
    assert "document_ids" in validation.type_mismatches
    assert "answer" in validation.fallbacks_applied
    assert validation.degraded is True


def test_validate_preserves_response_object():
    """Test that the response object is returned (possibly modified)."""
    response = MockResponse(question="What is X?", answer="X is Y.")

    required_fields = {
        "question": str,
        "answer": str,
    }

    result, validation = validate_llm_response(response, required_fields)

    # Should be the same object or at least a compatible one
    assert result.question == response.question
    assert result.answer == response.answer
