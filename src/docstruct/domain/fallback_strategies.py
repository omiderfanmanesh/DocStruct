"""Per-field fallback strategies for LLM response validation.

Defines factory functions that provide default values when LLM responses
have missing, None, or incorrectly typed fields. Each strategy is callable
and returns a fallback value appropriate for its field.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docstruct.domain.models.search import SearchDocumentIndex


def fallback_rewritten_question(original_question: str) -> str:
    """Fallback for rewritten_question field: use original question.

    Args:
        original_question: The user's original question

    Returns:
        The original question unchanged
    """
    return original_question


def fallback_inferred_document_ids(candidate_document_ids: list[str]) -> list[str]:
    """Fallback for inferred_document_ids field: return all candidate IDs.

    When the LLM cannot infer which documents are relevant, fall back to
    using all candidates. This is more conservative than discarding all
    document hints.

    Args:
        candidate_document_ids: All available candidate document IDs

    Returns:
        The full list of candidate document IDs
    """
    return candidate_document_ids if candidate_document_ids else []


def fallback_document_ids(candidate_document_ids: list[str]) -> list[str]:
    """Fallback for document_ids field: return all candidate IDs.

    When document selection fails, use all candidates for context retrieval.

    Args:
        candidate_document_ids: All available candidate document IDs

    Returns:
        The full list of candidate document IDs
    """
    return candidate_document_ids if candidate_document_ids else []


def fallback_node_ids(effective_question: str, document: SearchDocumentIndex, limit: int = 4) -> list[str]:
    """Fallback for node_ids field: use heuristic node matching.

    When intelligent node selection fails, fall back to a heuristic approach
    based on keyword matching and document structure.

    Args:
        effective_question: The question being answered
        document: The document to select nodes from
        limit: Maximum number of nodes to return

    Returns:
        List of node IDs selected by heuristic matching
    """
    # Import here to avoid circular imports
    from docstruct.domain.pageindex_search import fallback_node_matches

    return fallback_node_matches(effective_question, document, limit=limit)


def fallback_answer() -> str:
    """Fallback for answer field: return a generic unable-to-answer message.

    When answer synthesis fails, provide a user-friendly message indicating
    the pipeline could not formulate a grounded answer.

    Returns:
        A generic fallback answer string
    """
    return "I found relevant document nodes, but I could not synthesize a grounded answer."


def fallback_citations() -> list:
    """Fallback for citations field: return empty list.

    When citation extraction fails, it's better to return an answer without
    citations than to crash. The degraded flag will be set to indicate
    reduced response quality.

    Returns:
        An empty list of citations
    """
    return []


def create_fallback_strategies_for_rewrite(original_question: str) -> dict[str, callable]:
    """Factory for fallback strategies for the rewrite_question node.

    Args:
        original_question: The user's original question

    Returns:
        Dict mapping field names to fallback callables
    """
    return {
        "rewritten_question": lambda: fallback_rewritten_question(original_question),
    }


def create_fallback_strategies_for_document_selection(
    candidate_document_ids: list[str],
) -> dict[str, callable]:
    """Factory for fallback strategies for the select_documents node.

    Args:
        candidate_document_ids: Available candidate document IDs

    Returns:
        Dict mapping field names to fallback callables
    """
    return {
        "document_ids": lambda: fallback_document_ids(candidate_document_ids),
    }


def create_fallback_strategies_for_node_selection(
    effective_question: str,
    document: SearchDocumentIndex,
) -> dict[str, callable]:
    """Factory for fallback strategies for the select_nodes agent call.

    Args:
        effective_question: The question being answered
        document: The document to select nodes from

    Returns:
        Dict mapping field names to fallback callables
    """
    return {
        "node_ids": lambda: fallback_node_ids(effective_question, document, limit=4),
    }


def create_fallback_strategies_for_answer_synthesis() -> dict[str, callable]:
    """Factory for fallback strategies for the answer_from_contexts node.

    Returns:
        Dict mapping field names to fallback callables
    """
    return {
        "answer": fallback_answer,
        "citations": fallback_citations,
    }
