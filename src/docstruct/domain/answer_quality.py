"""Answer quality safeguards: hallucination detection, confidence scoring, empty-context guard."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class AnswerQualityReport:
    """Quality assessment of a generated answer."""

    confidence_score: float  # 0.0 to 1.0
    confidence_label: str    # "high", "medium", "low", "insufficient"
    has_grounded_citations: bool
    citation_coverage: float  # Fraction of citations that map to real context
    potential_hallucination: bool
    hallucination_indicators: list[str]
    empty_context: bool
    warnings: list[str]


def assess_answer_quality(
    answer: str,
    citations: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    *,
    question: str = "",
) -> AnswerQualityReport:
    """Assess the quality and grounding of a generated answer.

    Args:
        answer: The LLM-generated answer text.
        citations: List of citation dicts from the LLM.
        contexts: List of context blocks that were provided to the LLM.
        question: Original question for relevance checking.

    Returns:
        AnswerQualityReport with confidence scoring and hallucination flags.
    """
    warnings: list[str] = []
    hallucination_indicators: list[str] = []

    # Check for empty/insufficient context
    if not contexts:
        return AnswerQualityReport(
            confidence_score=0.0,
            confidence_label="insufficient",
            has_grounded_citations=False,
            citation_coverage=0.0,
            potential_hallucination=True,
            hallucination_indicators=["No context provided to ground the answer."],
            empty_context=True,
            warnings=["Answer generated without any context blocks."],
        )

    context_texts = " ".join(str(ctx.get("text", "")) for ctx in contexts).lower()
    context_node_ids = {str(ctx.get("node_id", "")) for ctx in contexts if ctx.get("node_id")}
    context_doc_ids = {str(ctx.get("document_id", "")) for ctx in contexts if ctx.get("document_id")}

    # Check for meaningful context content
    if len(context_texts.strip()) < 50:
        warnings.append("Context blocks contain very little text.")

    # Validate citations against provided contexts
    grounded_citations = 0
    for citation in citations:
        cit_node_id = str(citation.get("node_id", ""))
        cit_doc_id = str(citation.get("document_id", ""))
        if cit_node_id in context_node_ids or cit_doc_id in context_doc_ids:
            grounded_citations += 1
        else:
            hallucination_indicators.append(
                f"Citation references node_id='{cit_node_id}' not found in provided contexts."
            )

    citation_coverage = grounded_citations / len(citations) if citations else 0.0
    has_grounded_citations = grounded_citations > 0

    # Check for hallucination indicators in the answer text
    answer_lower = answer.lower()

    # Detect fabricated specifics not in context
    _check_fabricated_numbers(answer_lower, context_texts, hallucination_indicators)
    _check_fabricated_names(answer, contexts, hallucination_indicators)

    # Detect hedging language that suggests uncertainty
    hedging_count = _count_hedging_phrases(answer_lower)
    if hedging_count >= 3:
        warnings.append("Answer contains heavy hedging language suggesting low confidence.")

    # Detect overconfident patterns with no grounding
    if not has_grounded_citations and not _answer_acknowledges_limitation(answer_lower):
        hallucination_indicators.append(
            "Answer does not cite sources and does not acknowledge any limitations."
        )

    # Calculate confidence score
    confidence_score = _calculate_confidence(
        answer=answer,
        citation_coverage=citation_coverage,
        has_grounded_citations=has_grounded_citations,
        context_text_length=len(context_texts.strip()),
        hallucination_count=len(hallucination_indicators),
        hedging_count=hedging_count,
    )

    potential_hallucination = len(hallucination_indicators) > 0

    # Determine confidence label
    if confidence_score >= 0.75:
        confidence_label = "high"
    elif confidence_score >= 0.5:
        confidence_label = "medium"
    elif confidence_score >= 0.25:
        confidence_label = "low"
    else:
        confidence_label = "insufficient"

    return AnswerQualityReport(
        confidence_score=round(confidence_score, 3),
        confidence_label=confidence_label,
        has_grounded_citations=has_grounded_citations,
        citation_coverage=round(citation_coverage, 3),
        potential_hallucination=potential_hallucination,
        hallucination_indicators=hallucination_indicators,
        empty_context=False,
        warnings=warnings,
    )


def _check_fabricated_numbers(
    answer_lower: str,
    context_texts: str,
    indicators: list[str],
) -> None:
    """Check if the answer contains specific numbers/dates not found in context."""
    # Find dates in answer (DD/MM/YYYY, Month Day, etc.)
    date_patterns = [
        re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"),
        re.compile(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b", re.IGNORECASE),
    ]
    for pattern in date_patterns:
        for match in pattern.finditer(answer_lower):
            date_str = match.group()
            if date_str not in context_texts:
                indicators.append(
                    f"Date '{date_str}' in answer not found in provided context."
                )

    # Find euro amounts
    euro_pattern = re.compile(r"€\s*[\d,.]+|\d+(?:[.,]\d+)?\s*(?:euros?|€)")
    for match in euro_pattern.finditer(answer_lower):
        amount = match.group()
        # Extract just the number for fuzzy matching
        number = re.sub(r"[^\d.,]", "", amount)
        if number and number not in context_texts:
            indicators.append(
                f"Amount '{amount}' in answer not found in provided context."
            )


def _check_fabricated_names(
    answer: str,
    contexts: list[dict[str, Any]],
    indicators: list[str],
) -> None:
    """Check if the answer references entity names not in the context."""
    context_text_combined = " ".join(
        f"{ctx.get('text', '')} {ctx.get('document_title', '')} {ctx.get('node_title', '')}"
        for ctx in contexts
    ).lower()

    # Check for university names in answer not in context
    uni_pattern = re.compile(r"University of [A-Z][A-Za-z''.\-]+(?: [A-Z][A-Za-z''.\-]+){0,3}", re.IGNORECASE)
    for match in uni_pattern.finditer(answer):
        name = match.group().lower()
        if name not in context_text_combined:
            indicators.append(
                f"University name '{match.group()}' in answer not found in provided context."
            )


def _count_hedging_phrases(text: str) -> int:
    """Count hedging/uncertainty phrases in the text."""
    hedging_phrases = [
        "i'm not sure",
        "i am not sure",
        "it seems",
        "it appears",
        "possibly",
        "perhaps",
        "might be",
        "may be",
        "could be",
        "i think",
        "not certain",
        "unclear",
        "hard to say",
        "difficult to determine",
    ]
    return sum(1 for phrase in hedging_phrases if phrase in text)


def _answer_acknowledges_limitation(text: str) -> bool:
    """Check if the answer explicitly acknowledges insufficient information."""
    limitation_phrases = [
        "not enough",
        "insufficient",
        "cannot find",
        "could not find",
        "no information",
        "not mentioned",
        "not specified",
        "not available",
        "not provided",
        "i need more",
        "please specify",
        "clarif",
    ]
    return any(phrase in text for phrase in limitation_phrases)


def _calculate_confidence(
    *,
    answer: str,
    citation_coverage: float,
    has_grounded_citations: bool,
    context_text_length: int,
    hallucination_count: int,
    hedging_count: int,
) -> float:
    """Calculate a confidence score from 0.0 to 1.0."""
    score = 0.5  # Base score

    # Citation grounding (up to +0.3)
    if has_grounded_citations:
        score += 0.15
        score += citation_coverage * 0.15

    # Context quality (up to +0.15)
    if context_text_length > 200:
        score += 0.1
    if context_text_length > 500:
        score += 0.05

    # Hallucination penalty (up to -0.4)
    score -= min(hallucination_count * 0.1, 0.4)

    # Hedging penalty (up to -0.15)
    score -= min(hedging_count * 0.05, 0.15)

    # Answer length penalty (very short answers are suspicious)
    if len(answer.strip()) < 20:
        score -= 0.1

    # Acknowledgment of limitations (slight positive if honest)
    if _answer_acknowledges_limitation(answer.lower()):
        score += 0.05

    return max(0.0, min(1.0, score))


def guard_empty_context(contexts: list[dict[str, Any]]) -> str | None:
    """Return a safe message if contexts are empty or lack meaningful text.

    Returns:
        None if contexts are sufficient, or a fallback message string.
    """
    if not contexts:
        return "I could not find any relevant document sections to answer this question."

    total_text = sum(len(str(ctx.get("text", ""))) for ctx in contexts)
    if total_text < 30:
        return (
            "The retrieved document sections contain too little text to provide a reliable answer. "
            "Please try rephrasing your question or specifying a different document scope."
        )
    return None
