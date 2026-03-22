"""LLM agent that performs document selection, tree search, and answer synthesis."""

from __future__ import annotations

import json

from docstruct.application.ports import LLMPort
from docstruct.config import AgentConfig
from docstruct.domain.models import SearchAnswer, SearchCitation, SearchDocumentIndex
from docstruct.domain.pageindex_search import build_tree_outline


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _parse_json_payload(raw: str) -> dict:
    cleaned = _strip_code_fences(raw)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


class PageIndexSearchAgent:
    def __init__(self, client: LLMPort):
        config = AgentConfig.from_env()
        self._client = client
        self._model = config.model
        self._max_tokens = min(config.max_tokens, 4096)

    def _call_json(self, prompt: str, *, max_tokens: int = 900) -> dict:
        raw = self._client.create_message(
            model=self._model,
            max_tokens=min(max_tokens, self._max_tokens),
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json_payload(raw)

    def select_documents(
        self,
        question: str,
        documents: list[SearchDocumentIndex],
    ) -> tuple[list[str], str | None]:
        if not documents:
            return [], None
        if len(documents) == 1:
            return [documents[0].document_id], "Single indexed document available."

        catalog = [
            {
                "document_id": document.document_id,
                "title": document.title,
                "summary": document.summary,
                "document_type": document.metadata.document_type if document.metadata else None,
                "organization": document.metadata.organization if document.metadata else None,
                "year": document.metadata.year if document.metadata else None,
                "doc_description": document.doc_description,
            }
            for document in documents
        ]
        response = self._call_json(
            (
                "You are selecting the most relevant documents for a grounded QA task.\n"
                "Choose at most 3 document_ids that are most likely to answer the question.\n"
                "Prefer precision over recall.\n\n"
                f"Question: {question}\n\n"
                f"Documents:\n{json.dumps(catalog, indent=2, ensure_ascii=False)}\n\n"
                'Return JSON with keys "thinking" and "document_ids".'
            )
        )
        valid_ids = {document.document_id for document in documents}
        selected_ids = [
            document_id
            for document_id in response.get("document_ids", [])
            if document_id in valid_ids
        ][:3]
        thinking = str(response.get("thinking") or "").strip() or None
        return selected_ids, thinking

    def select_nodes(
        self,
        question: str,
        document: SearchDocumentIndex,
    ) -> tuple[list[str], str | None]:
        outline = build_tree_outline(document.structure, max_nodes=80, preview_chars=160)
        response = self._call_json(
            (
                "You are searching a PageIndex-style document tree for the nodes most likely to answer a question.\n"
                "Pick at most 6 node_ids. Use titles, summaries, and text previews to reason carefully.\n\n"
                f"Question: {question}\n"
                f"Document title: {document.title}\n\n"
                f"Document tree:\n{json.dumps(outline, indent=2, ensure_ascii=False)}\n\n"
                'Return JSON with keys "thinking" and "node_ids".'
            ),
            max_tokens=1200,
        )
        valid_ids: set[str] = set()

        def collect_valid(items: list[dict]) -> None:
            for item in items:
                valid_ids.add(str(item.get("node_id")))
                collect_valid(list(item.get("nodes", [])))

        collect_valid(document.structure)
        node_ids = [node_id for node_id in response.get("node_ids", []) if node_id in valid_ids][:6]
        thinking = str(response.get("thinking") or "").strip() or None
        return node_ids, thinking

    def answer_from_contexts(
        self,
        question: str,
        contexts: list[dict],
        *,
        document_ids: list[str],
        retrieval_notes: str | None = None,
    ) -> SearchAnswer:
        response = self._call_json(
            (
                "Answer the user's question using only the provided context snippets.\n"
                "If the context is insufficient, say so clearly.\n"
                "Keep the answer concise and factual.\n\n"
                f"Question: {question}\n"
                f"Retrieval notes: {retrieval_notes or 'n/a'}\n\n"
                f"Context snippets:\n{json.dumps(contexts, indent=2, ensure_ascii=False)}\n\n"
                "Return JSON with keys:\n"
                '- "answer": string\n'
                '- "citations": list of objects with document_id, document_title, node_id, node_title, line_number\n'
            ),
            max_tokens=1400,
        )
        citations = []
        for citation_data in response.get("citations", []):
            try:
                citations.append(SearchCitation.from_dict(citation_data))
            except Exception:
                continue

        answer = str(response.get("answer") or "").strip()
        if not answer:
            answer = "I could not find enough grounded context to answer confidently."
        return SearchAnswer(
            question=question,
            answer=answer,
            citations=citations,
            document_ids=document_ids,
            retrieval_notes=retrieval_notes,
        )
