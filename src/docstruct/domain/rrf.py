"""Reciprocal Rank Fusion (RRF) score fusion for retrieval results."""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = 60,
    limit: int | None = None,
) -> list[tuple[str, float]]:
    """Fuse multiple ranked lists using Reciprocal Rank Fusion.

    RRF formula: score(d) = Σ 1/(k + rank(d))
    where rank is the 1-based position in each list.

    Args:
        ranked_lists: List of ranked ID lists. Each list is ordered by rank (best first).
                     IDs that don't appear in a list are excluded from that list's contribution.
        k: RRF constant (default 60). Higher k reduces rank differences.
        limit: Maximum number of results to return. If None, return all fused IDs.

    Returns:
        List of (id, rrf_score) tuples sorted by score descending.

    Example:
        >>> list1 = ["doc1", "doc2", "doc3"]
        >>> list2 = ["doc2", "doc1", "doc4"]
        >>> result = reciprocal_rank_fusion([list1, list2], k=60)
        # doc1: 1/(60+1) + 1/(60+2) = 0.0164 + 0.0159 = 0.0323
        # doc2: 1/(60+2) + 1/(60+1) = 0.0159 + 0.0164 = 0.0323
        # doc3: 1/(60+3) = 0.0154
        # doc4: 1/(60+3) = 0.0154
    """
    # Skip empty lists
    non_empty_lists = [lst for lst in ranked_lists if lst]
    if not non_empty_lists:
        return []

    # Calculate scores
    scores: dict[str, float] = {}

    for ranked_list in non_empty_lists:
        for rank_index, item_id in enumerate(ranked_list, start=1):
            if item_id not in scores:
                scores[item_id] = 0.0
            # 1-based rank
            scores[item_id] += 1.0 / (k + rank_index)

    # Sort by score descending
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Apply limit if specified
    if limit is not None:
        sorted_scores = sorted_scores[:limit]

    return sorted_scores
