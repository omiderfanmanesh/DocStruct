"""LLM agent that performs document selection, tree search, and answer synthesis."""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from docstruct.application.ports import LLMPort
from docstruct.config import AgentConfig
from docstruct.domain.models import (
    SearchAnswer,
    SearchCitation,
    SearchDocumentIndex,
    SearchSelectionDecision,
)
from docstruct.domain.pageindex_search import (
    build_document_scope_clues,
    build_document_identity_terms,
    build_document_scope_label,
    build_search_profile,
    build_scope_options,
    build_tree_outline,
)
from docstruct.infrastructure.llm.structured_output import invoke_structured


class _RewriteQuestionPayload(BaseModel):
    rewritten_question: Optional[str] = None
    reasoning: Optional[str] = None
    inferred_document_ids: List[str] = Field(default_factory=list)


class _DocumentSelectionPayload(BaseModel):
    thinking: Optional[str] = None
    document_ids: List[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarifying_question: Optional[str] = None


class _NodeSelectionPayload(BaseModel):
    thinking: Optional[str] = None
    node_ids: List[str] = Field(default_factory=list)


class _AnswerPayload(BaseModel):
    answer: Optional[str] = None
    citations: List[Dict] = Field(default_factory=list)
    clarification_needed: bool = False
    clarifying_question: Optional[str] = None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


class PageIndexSearchAgent:
    def __init__(self, client: LLMPort):
        config = AgentConfig.from_env()
        self._client = client
        self._model = config.model
        self._max_tokens = min(config.max_tokens, 4096)

    def _call_structured(self, prompt: str, *, schema, max_tokens: int = 900):
        return invoke_structured(
            self._client,
            model=self._model,
            max_tokens=min(max_tokens, self._max_tokens),
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
        )

    def rewrite_question(
        self,
        question: str,
        documents: list[SearchDocumentIndex],
    ) -> tuple[str, str | None, list[str]]:
        if not documents:
            return question, None, []

        catalog = [
            {
                "document_id": document.document_id,
                "title": document.title,
                "scope_label": build_document_scope_label(document),
                "search_profile": build_search_profile(document).to_dict(),
                "identity_terms": build_document_identity_terms(document)[:6],
                "scope_clues": build_document_scope_clues(document)[:6],
                "summary": document.summary,
            }
            for document in documents[:12]
        ]
        response = self._call_structured(
            (
                "Rewrite the user's question for retrieval using a HyPE-style expansion.\n"
                "Your job is to infer the likely intended document scope from the catalog and rewrite the question so retrieval becomes easier.\n"
                "Rules:\n"
                "- Use only scope hints supported by the catalog.\n"
                "- Do not invent dates, requirements, or facts.\n"
                "- If the user wording already has enough scope, keep the rewrite very close to the original.\n"
                "- If the intended scope is still ambiguous, keep the question close to the original instead of forcing a guess.\n\n"
                f"Original question: {question}\n\n"
                f"Document catalog:\n{json.dumps(catalog, indent=2, ensure_ascii=False)}\n\n"
                "Return JSON with keys:\n"
                '- "rewritten_question": string\n'
                '- "reasoning": string\n'
                '- "inferred_document_ids": array of strings\n'
            ),
            schema=_RewriteQuestionPayload,
            max_tokens=1200,
        )
        valid_ids = {document.document_id for document in documents}
        inferred_document_ids = [
            document_id
            for document_id in response.inferred_document_ids
            if document_id in valid_ids
        ][:2]
        rewritten_question = str(response.rewritten_question or "").strip() or question
        reasoning = str(response.reasoning or "").strip() or None
        return rewritten_question, reasoning, inferred_document_ids

    def select_documents(
        self,
        question: str,
        documents: list[SearchDocumentIndex],
    ) -> SearchSelectionDecision:
        if not documents:
            return SearchSelectionDecision()
        if len(documents) == 1:
            return SearchSelectionDecision(
                document_ids=[documents[0].document_id],
                thinking="Single indexed document available.",
            )

        catalog = [
            {
                "document_id": document.document_id,
                "title": document.title,
                "scope_label": build_document_scope_label(document),
                "search_profile": build_search_profile(document).to_dict(),
                "identity_terms": build_document_identity_terms(document)[:6],
                "scope_clues": build_document_scope_clues(document)[:6],
                "summary": document.summary,
                "document_type": document.metadata.document_type if document.metadata else None,
                "organization": document.metadata.organization if document.metadata else None,
                "year": document.metadata.year if document.metadata else None,
                "doc_description": document.doc_description,
            }
            for document in documents
        ]
        response = self._call_structured(
            (
                "You are selecting policy documents for grounded QA.\n"
                "These documents may belong to different universities, regions, or issuing organizations.\n"
                "Treat each document scope as separate unless the user explicitly asks for a comparison.\n"
                "If the question is ambiguous and could refer to multiple scopes, do not guess.\n"
                "Instead, set needs_clarification=true and ask a short clarifying question.\n"
                "Choose at most 3 document_ids only when you can justify them confidently.\n"
                "Prefer precision over recall.\n\n"
                f"Question: {question}\n\n"
                f"Documents:\n{json.dumps(catalog, indent=2, ensure_ascii=False)}\n\n"
                "Return JSON with keys:\n"
                '- "thinking": string\n'
                '- "document_ids": array of strings\n'
                '- "needs_clarification": boolean\n'
                '- "clarifying_question": string or null\n'
            ),
            schema=_DocumentSelectionPayload,
        )
        valid_ids = {document.document_id for document in documents}
        selected_ids = [
            document_id
            for document_id in response.document_ids
            if document_id in valid_ids
        ][:3]
        thinking = str(response.thinking or "").strip() or None
        needs_clarification = _as_bool(response.needs_clarification)
        clarifying_question = str(response.clarifying_question or "").strip() or None
        if needs_clarification and not clarifying_question:
            options = "; ".join(build_scope_options(documents))
            clarifying_question = f"Which university, region, or issuer should I use: {options}?"
        if needs_clarification:
            selected_ids = []
        return SearchSelectionDecision(
            document_ids=selected_ids,
            thinking=thinking,
            needs_clarification=needs_clarification,
            clarifying_question=clarifying_question,
        )

    def select_nodes(
        self,
        question: str,
        document: SearchDocumentIndex,
    ) -> tuple[list[str], str | None]:
        outline = build_tree_outline(document.structure, max_nodes=80, preview_chars=160)
        response = self._call_structured(
            (
                "You are searching a PageIndex-style document tree for the nodes most likely to answer a question.\n"
                "Pick at most 6 node_ids. Use titles, summaries, and text previews to reason carefully.\n\n"
                f"Question: {question}\n"
                f"Document title: {document.title}\n\n"
                f"Document tree:\n{json.dumps(outline, indent=2, ensure_ascii=False)}\n\n"
                'Return JSON with keys "thinking" and "node_ids".'
            ),
            schema=_NodeSelectionPayload,
            max_tokens=1200,
        )
        valid_ids: set[str] = set()

        def collect_valid(items: list[dict]) -> None:
            for item in items:
                valid_ids.add(str(item.get("node_id")))
                collect_valid(list(item.get("nodes", [])))

        collect_valid(document.structure)
        node_ids = [node_id for node_id in response.node_ids if node_id in valid_ids][:6]
        thinking = str(response.thinking or "").strip() or None
        return node_ids, thinking

    def answer_from_contexts(
        self,
        question: str,
        contexts: list[dict],
        *,
        document_ids: list[str],
        retrieval_notes: str | None = None,
    ) -> SearchAnswer:
        response = self._call_structured(
            (
                "Answer the user's question using only the provided context snippets.\n"
                "Important guardrails:\n"
                "- The snippets may come from different universities, regions, or issuing organizations.\n"
                "- Never merge policies across different scopes into one answer unless the user explicitly asked for a comparison.\n"
                "- If the question is underspecified for the provided scopes, return clarification_needed=true.\n"
                "- If the context is insufficient, say so clearly and do not invent facts.\n"
                "Keep the answer concise, factual, and grounded.\n\n"
                f"Question: {question}\n"
                f"Retrieval notes: {retrieval_notes or 'n/a'}\n\n"
                f"Context snippets:\n{json.dumps(contexts, indent=2, ensure_ascii=False)}\n\n"
                "Return JSON with keys:\n"
                '- "answer": string\n'
                '- "citations": list of objects with document_id, document_title, node_id, node_title, line_number\n'
                '- "clarification_needed": boolean\n'
                '- "clarifying_question": string or null\n'
            ),
            schema=_AnswerPayload,
            max_tokens=1400,
        )
        citations = []
        for citation_data in response.citations:
            try:
                citations.append(SearchCitation.from_dict(citation_data))
            except Exception:
                continue

        clarification_needed = _as_bool(response.clarification_needed)
        clarifying_question = str(response.clarifying_question or "").strip() or None
        answer = str(response.answer or "").strip()
        if clarification_needed and not answer:
            answer = clarifying_question or "I need the university, region, or issuing organization before I can answer safely."
        if not answer:
            answer = "I could not find enough grounded context to answer confidently."
        return SearchAnswer(
            question=question,
            answer=answer,
            citations=citations,
            document_ids=document_ids,
            retrieval_notes=retrieval_notes,
            needs_clarification=clarification_needed,
            clarifying_question=clarifying_question,
        )
