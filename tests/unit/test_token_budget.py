"""Unit tests for TokenBudget token allocation and enforcement."""

import pytest

from docstruct.domain.token_budget import TokenBudget


def test_token_budget_initialization():
    """Test TokenBudget initialization with valid parameters."""
    budget = TokenBudget(max_tokens=1000)

    assert budget.max_tokens == 1000
    assert budget.used_tokens == 0
    assert budget.overflow_policy == "truncate"
    assert budget.remaining == 1000
    assert budget.is_exceeded is False


def test_token_budget_initialization_with_reject_policy():
    """Test TokenBudget initialization with reject overflow policy."""
    budget = TokenBudget(max_tokens=500, overflow_policy="reject")

    assert budget.overflow_policy == "reject"
    assert budget.remaining == 500


def test_token_budget_invalid_max_tokens():
    """Test that TokenBudget rejects non-positive max_tokens."""
    with pytest.raises(ValueError, match="max_tokens must be > 0"):
        TokenBudget(max_tokens=0)

    with pytest.raises(ValueError, match="max_tokens must be > 0"):
        TokenBudget(max_tokens=-100)


def test_token_budget_invalid_overflow_policy():
    """Test that TokenBudget rejects invalid overflow policies."""
    with pytest.raises(ValueError, match="overflow_policy must be 'truncate' or 'reject'"):
        TokenBudget(max_tokens=1000, overflow_policy="fail")

    with pytest.raises(ValueError, match="overflow_policy must be 'truncate' or 'reject'"):
        TokenBudget(max_tokens=1000, overflow_policy="drop")


def test_estimate_tokens_simple():
    """Test token estimation for simple text."""
    budget = TokenBudget(max_tokens=100)

    # 1 token ≈ 4 characters: "Hello" (5 chars) = 2 tokens (5 // 4 = 1, but min 1)
    assert budget.estimate_tokens("Hello") == 2
    assert budget.estimate_tokens("This is a test") == 4
    assert budget.estimate_tokens("A") == 1  # min 1 token


def test_estimate_tokens_empty_string():
    """Test that empty strings estimate to 1 token minimum."""
    budget = TokenBudget(max_tokens=100)

    assert budget.estimate_tokens("") == 1


def test_estimate_tokens_long_text():
    """Test token estimation for long text."""
    budget = TokenBudget(max_tokens=10000)

    long_text = "A" * 400  # 400 chars = 100 tokens
    assert budget.estimate_tokens(long_text) == 100

    long_text = "A" * 399  # 399 chars = 99 tokens (399 // 4)
    assert budget.estimate_tokens(long_text) == 99


def test_add_item_fits_in_budget():
    """Test adding items that fit within the budget."""
    budget = TokenBudget(max_tokens=100)

    # Add 30 tokens
    assert budget.add("item1", 30) is True
    assert budget.used_tokens == 30
    assert budget.remaining == 70

    # Add another 40 tokens
    assert budget.add("item2", 40) is True
    assert budget.used_tokens == 70
    assert budget.remaining == 30


def test_add_item_exceeds_budget_truncate_policy():
    """Test adding item that exceeds budget with truncate policy."""
    budget = TokenBudget(max_tokens=100, overflow_policy="truncate")

    budget.add("item1", 80)
    assert budget.add("item2", 30) is False
    assert budget.used_tokens == 80
    assert "item2" in budget.excluded_items
    assert budget.remaining == 20


def test_add_item_exceeds_budget_reject_policy():
    """Test adding item that exceeds budget with reject policy."""
    budget = TokenBudget(max_tokens=100, overflow_policy="reject")

    budget.add("item1", 80)
    with pytest.raises(TokenBudget.TokenBudgetExceeded):
        budget.add("item2", 30)

    # Budget should remain unchanged after failed add
    assert budget.used_tokens == 80


def test_add_item_exactly_fills_budget():
    """Test adding item that exactly fills remaining budget."""
    budget = TokenBudget(max_tokens=100)

    budget.add("item1", 60)
    assert budget.add("item2", 40) is True
    assert budget.used_tokens == 100
    assert budget.remaining == 0


def test_can_fit_method():
    """Test can_fit() method for budget checking."""
    budget = TokenBudget(max_tokens=100)

    assert budget.can_fit(50) is True
    budget.add("item1", 50)
    assert budget.can_fit(50) is True
    assert budget.can_fit(51) is False


def test_utilization_property():
    """Test utilization property calculation."""
    budget = TokenBudget(max_tokens=100)

    assert budget.utilization == 0.0
    budget.add("item1", 50)
    assert budget.utilization == 0.5
    budget.add("item2", 50)
    assert budget.utilization == 1.0


def test_is_exceeded_property():
    """Test is_exceeded property."""
    budget = TokenBudget(max_tokens=100)

    assert budget.is_exceeded is False
    budget.add("item1", 100)
    assert budget.is_exceeded is False
    # Directly manipulate to test the property
    budget.used_tokens = 101
    assert budget.is_exceeded is True


def test_validate_prompt_within_limit():
    """Test prompt validation when within context window."""
    budget = TokenBudget(max_tokens=1000)

    assert budget.validate_prompt(prompt_tokens=300, max_response_tokens=400, model_limit=1000) is True
    assert budget.validate_prompt(prompt_tokens=500, max_response_tokens=500, model_limit=1000) is True


def test_validate_prompt_exceeds_limit():
    """Test prompt validation when exceeding context window."""
    budget = TokenBudget(max_tokens=1000)

    assert budget.validate_prompt(prompt_tokens=600, max_response_tokens=500, model_limit=1000) is False
    assert budget.validate_prompt(prompt_tokens=500, max_response_tokens=600, model_limit=1000) is False


def test_validate_prompt_exactly_at_limit():
    """Test prompt validation at exact context window boundary."""
    budget = TokenBudget(max_tokens=1000)

    assert budget.validate_prompt(prompt_tokens=600, max_response_tokens=400, model_limit=1000) is True


def test_multiple_item_tracking():
    """Test tracking of multiple items in the budget."""
    budget = TokenBudget(max_tokens=100)

    items = [("item1", 20), ("item2", 15), ("item3", 25)]

    for item_id, tokens in items:
        added = budget.add(item_id, tokens)
        assert added is True

    assert budget.used_tokens == 60
    assert len(budget._items) == 3


def test_excluded_items_tracking():
    """Test that excluded items are tracked correctly."""
    budget = TokenBudget(max_tokens=100, overflow_policy="truncate")

    budget.add("item1", 80)
    budget.add("item2", 30)  # Excluded
    budget.add("item3", 10)  # Excluded

    assert len(budget.excluded_items) == 2
    assert "item2" in budget.excluded_items
    assert "item3" in budget.excluded_items
    assert "item1" not in budget.excluded_items


def test_reject_policy_error_message():
    """Test that reject policy provides informative error message."""
    budget = TokenBudget(max_tokens=100, overflow_policy="reject")

    budget.add("item1", 60)

    try:
        budget.add("item2", 50)
        assert False, "Should have raised TokenBudgetExceeded"
    except TokenBudget.TokenBudgetExceeded as exc:
        assert "50" in str(exc)
        assert "100" in str(exc)
        assert "60" in str(exc)


def test_estimate_tokens_with_special_characters():
    """Test token estimation with special characters."""
    budget = TokenBudget(max_tokens=1000)

    # Special characters count toward length
    text_with_special = "Hello!@#$%^&*()[]{}|\\<>?,.;:'\""
    tokens = budget.estimate_tokens(text_with_special)
    assert tokens >= 8  # (36 chars // 4 = 9, min 1)


def test_remaining_never_negative():
    """Test that remaining property never returns negative values."""
    budget = TokenBudget(max_tokens=100)

    # Directly set used_tokens beyond max (shouldn't happen in normal use)
    budget.used_tokens = 150
    assert budget.remaining == 0  # Should cap at 0, not return -50


def test_zero_token_add():
    """Test adding items with minimal (1 token) estimates."""
    budget = TokenBudget(max_tokens=100)

    # Estimate for very short text
    small_tokens = budget.estimate_tokens("x")
    assert small_tokens == 1
    assert budget.add("small_item", 1) is True
    assert budget.used_tokens == 1
