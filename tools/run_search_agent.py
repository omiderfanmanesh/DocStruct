#!/usr/bin/env python
"""Ask grounded questions across indexed documents and save the answer artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import re
import sys

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docstruct.application.pageindex_workflow import answer_question
from docstruct.infrastructure.llm.factory import build_client
from docstruct.output_layout import ANSWERS_DIR, PAGEINDEX_DIR, ensure_output_layout, slugify


def _truncate(value: object, *, max_chars: int = 120) -> str:
    text = str(value)
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _format_step_details(step: dict) -> str:
    details = step.get("details") or {}
    stage = step.get("stage", "")

    if stage == "load_indexes":
        return f"{details.get('count', 0)} indexes"
    if stage == "intent_detection":
        return "multi-doc intent" if details.get("multi_document_intent") else "single-scope intent"
    if stage in {"initial_ranking", "candidate_ranking", "selected_documents"}:
        candidates = details.get("candidates") or details.get("selected_documents") or []
        labels = [item.get("scope_label") or item.get("document_id") for item in candidates[:3] if isinstance(item, dict)]
        return ", ".join(_truncate(label, max_chars=50) for label in labels if label) or "no candidates"
    if stage == "rewrite_question":
        rewritten = details.get("rewritten_question")
        if rewritten:
            return _truncate(rewritten)
        return "used original question"
    if stage == "document_selection":
        selected = details.get("selected_document_ids") or []
        if selected:
            return ", ".join(_truncate(item, max_chars=40) for item in selected[:4])
        if details.get("needs_clarification"):
            return _truncate(details.get("clarifying_question") or "clarification requested")
        return "no selection"
    if stage in {"node_selection", "fallback_nodes"}:
        document_id = details.get("document_id") or "document"
        node_ids = details.get("node_ids") or []
        suffix = ", ".join(str(node_id) for node_id in node_ids[:4]) if node_ids else "no nodes"
        return f"{_truncate(document_id, max_chars=40)} -> {suffix}"
    if stage == "context_building":
        return f"{details.get('context_count', 0)} contexts"
    if stage == "clarification_gate":
        return _truncate(details.get("clarifying_question") or "clarification requested")
    if stage == "answer_synthesis":
        return _truncate(details.get("answer_preview") or "")

    if details:
        key, value = next(iter(details.items()))
        return f"{key}={_truncate(value, max_chars=60)}"
    return ""


def _print_trace(answer_payload: dict) -> None:
    trace = answer_payload.get("trace") or []
    if not trace:
        print("No verbose trace available.")
        return

    print("Search trace:")
    for index, step in enumerate(trace, start=1):
        stage = step.get("stage", "unknown")
        message = step.get("message", "")
        detail_summary = _format_step_details(step)
        suffix = f" ({detail_summary})" if detail_summary else ""
        print(f"{index}. [{stage}] {message}{suffix}")


def _print_backend_trace(label: str, answer_payload: dict) -> None:
    print(f"{label} trace:")
    _print_trace(answer_payload)


def _terminal_payload(answer_payload: dict, *, include_trace: bool) -> dict:
    if include_trace:
        return answer_payload
    filtered = dict(answer_payload)
    filtered.pop("trace", None)
    return filtered


def _tokenize_for_similarity(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _answer_similarity(left: str, right: str) -> float:
    left_tokens = _tokenize_for_similarity(left)
    right_tokens = _tokenize_for_similarity(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def _score_answer(answer_payload: dict) -> dict[str, object]:
    answer_text = str(answer_payload.get("answer") or "")
    citations = list(answer_payload.get("citations") or [])
    lowered = answer_text.lower()

    concrete_terms = (
        "isee",
        "pec",
        "form 1",
        "valid id",
        "identity",
        "certificate",
        "certification",
        "household",
        "disability",
        "abroad",
    )
    concrete_hits = sum(1 for term in concrete_terms if term in lowered)
    generic_markers = (
        "specific documentation is required",
        "certain circumstances",
        "more information would be needed",
        "does not explicitly list",
    )
    score = 0
    if citations:
        score += 1
    if "\n-" in answer_text or "\n1." in answer_text or answer_text.startswith("Required items:"):
        score += 1
    if concrete_hits >= 4:
        score += 2
    elif concrete_hits >= 2:
        score += 1
    if any(marker in lowered for marker in generic_markers):
        score -= 1

    return {
        "score": score,
        "citations": len(citations),
        "concrete_hits": concrete_hits,
    }


def _build_compare_summary(pageindex_payload: dict, neo4j_payload: dict) -> dict[str, object]:
    similarity = _answer_similarity(
        str(pageindex_payload.get("answer") or ""),
        str(neo4j_payload.get("answer") or ""),
    )
    pageindex_score = _score_answer(pageindex_payload)
    neo4j_score = _score_answer(neo4j_payload)

    if pageindex_score["score"] > neo4j_score["score"]:
        winner = "pageindex"
    elif neo4j_score["score"] > pageindex_score["score"]:
        winner = "neo4j"
    else:
        winner = "tie"

    return {
        "winner": winner,
        "similarity": round(similarity, 3),
        "answers_converged": similarity >= 0.9,
        "pageindex": pageindex_score,
        "neo4j": neo4j_score,
    }


def main() -> None:
    if load_dotenv is not None:
        load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)

    parser = argparse.ArgumentParser(description="Ask the DocStruct document-search agent about indexed documents")
    parser.add_argument("question", help="Question to ask")
    parser.add_argument("--index-dir", "-i", default=str(PAGEINDEX_DIR), help="Directory containing PageIndex search indexes")
    parser.add_argument("--output", "-o", default=None, help="Optional explicit output JSON file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print a compact step-by-step search trace")
    parser.add_argument("--verbose-full", action="store_true", help="Print the full trace JSON in the terminal output")
    parser.add_argument(
        "--retrieval-backend",
        choices=("auto", "pageindex", "neo4j"),
        default="auto",
        help="Choose which retrieval backend to use",
    )
    parser.add_argument(
        "--compare-backends",
        action="store_true",
        help="Run both pageindex and neo4j retrieval backends and save both answers",
    )
    args = parser.parse_args()

    if args.compare_backends and args.retrieval_backend != "auto":
        parser.error("--compare-backends cannot be combined with --retrieval-backend")

    layout = ensure_output_layout(PROJECT_ROOT)
    index_dir = Path(args.index_dir)
    if not index_dir.is_absolute():
        index_dir = (PROJECT_ROOT / index_dir).resolve()

    client = build_client()
    if args.compare_backends:
        pageindex_answer = answer_question(
            args.question,
            str(index_dir),
            client,
            retrieval_backend="pageindex",
        )
        neo4j_answer = answer_question(
            args.question,
            str(index_dir),
            client,
            retrieval_backend="neo4j",
        )
        compare_payload = {
            "question": args.question,
            "pageindex": pageindex_answer.to_dict(),
            "neo4j": neo4j_answer.to_dict(),
        }
        compare_payload["comparison"] = _build_compare_summary(
            compare_payload["pageindex"],
            compare_payload["neo4j"],
        )
    else:
        answer = answer_question(
            args.question,
            str(index_dir),
            client,
            retrieval_backend=args.retrieval_backend,
        )
        compare_payload = None

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = (PROJECT_ROOT / output_path).resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.compare_backends:
            output_path = layout["answers"] / f"{timestamp}_{slugify(args.question)}_compare.json"
        else:
            output_path = layout["answers"] / f"{timestamp}_{slugify(args.question)}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    terminal_payload = compare_payload if compare_payload is not None else answer.to_dict()
    output_path.write_text(json.dumps(terminal_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.compare_backends:
        if args.verbose:
            _print_backend_trace("pageindex", compare_payload["pageindex"])
            print()
            _print_backend_trace("neo4j", compare_payload["neo4j"])
            print()
        print(json.dumps(compare_payload if args.verbose_full else {
            "question": compare_payload["question"],
            "pageindex": _terminal_payload(compare_payload["pageindex"], include_trace=False),
            "neo4j": _terminal_payload(compare_payload["neo4j"], include_trace=False),
            "comparison": compare_payload["comparison"],
        }, indent=2, ensure_ascii=False))
    else:
        answer_payload = answer.to_dict()
        if args.verbose:
            _print_trace(answer_payload)
            print()
        print(json.dumps(_terminal_payload(answer_payload, include_trace=args.verbose_full), indent=2, ensure_ascii=False))
    print(f"\nSaved answer to: {output_path}")


if __name__ == "__main__":
    main()
