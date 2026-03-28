"""Token budget tracking and enforcement for context assembly."""

from __future__ import annotations


class TokenBudget:
    """Tracks and enforces token limits for context assembly and prompt construction.

    Uses character-based estimation (1 token ≈ 4 characters) as an approximation.
    Supports two overflow policies:
    - 'truncate': Drop lowest-priority contexts when budget exceeded (default)
    - 'reject': Raise TokenBudgetExceeded when budget would be exceeded
    """

    class TokenBudgetExceeded(Exception):
        """Raised when add() fails with reject policy."""

        pass

    def __init__(self, max_tokens: int, overflow_policy: str = "truncate") -> None:
        """Initialize token budget.

        Args:
            max_tokens: Maximum allowed tokens
            overflow_policy: 'truncate' or 'reject'

        Raises:
            ValueError: If max_tokens <= 0 or invalid overflow_policy
        """
        if max_tokens <= 0:
            raise ValueError("max_tokens must be > 0")
        if overflow_policy not in ("truncate", "reject"):
            raise ValueError("overflow_policy must be 'truncate' or 'reject'")

        self.max_tokens = max_tokens
        self.overflow_policy = overflow_policy
        self.used_tokens = 0
        self.excluded_items: list[str] = []
        self._items: dict[str, int] = {}  # item_id → tokens

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using character-based approximation.

        Uses: tokens ≈ len(text) // 4

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)

    def add(self, item_id: str, estimated_tokens: int) -> bool:
        """Try to add an item to the budget.

        Args:
            item_id: Unique identifier for this item
            estimated_tokens: Estimated token count for the item

        Returns:
            True if item fit within budget, False if excluded (truncate policy)

        Raises:
            TokenBudgetExceeded: If reject policy and item would exceed budget
        """
        if self.used_tokens + estimated_tokens <= self.max_tokens:
            # Item fits — add it
            self.used_tokens += estimated_tokens
            self._items[item_id] = estimated_tokens
            return True
        else:
            # Item doesn't fit
            if self.overflow_policy == "reject":
                raise self.TokenBudgetExceeded(
                    f"Adding {estimated_tokens} tokens would exceed budget of {self.max_tokens} "
                    f"(currently using {self.used_tokens})"
                )
            else:
                # truncate policy — exclude the item
                self.excluded_items.append(item_id)
                return False

    def can_fit(self, estimated_tokens: int) -> bool:
        """Check if an item with given tokens can fit in remaining budget.

        Args:
            estimated_tokens: Estimated token count

        Returns:
            True if there is enough remaining budget
        """
        return self.used_tokens + estimated_tokens <= self.max_tokens

    def validate_prompt(
        self,
        prompt_tokens: int,
        max_response_tokens: int,
        model_limit: int,
    ) -> bool:
        """Validate that assembled prompt fits within model's context window.

        Args:
            prompt_tokens: Token count of the prompt so far
            max_response_tokens: Token budget for the response
            model_limit: Model's maximum context window in tokens

        Returns:
            True if prompt + response fits within model_limit
        """
        return prompt_tokens + max_response_tokens <= model_limit

    @property
    def remaining(self) -> int:
        """Remaining tokens available in the budget."""
        return max(0, self.max_tokens - self.used_tokens)

    @property
    def is_exceeded(self) -> bool:
        """Whether the budget has been exceeded."""
        return self.used_tokens > self.max_tokens

    @property
    def utilization(self) -> float:
        """Current utilization as a fraction (0.0 to 1.0+)."""
        return self.used_tokens / self.max_tokens if self.max_tokens > 0 else 0.0
