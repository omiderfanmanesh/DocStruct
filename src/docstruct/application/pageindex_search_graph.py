"""LangGraph orchestration for multi-step PageIndex search QA."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from docstruct.application.agents.pageindex_search_agent import PageIndexSearchAgent
from docstruct.config import ContextConfig
from docstruct.domain.answer_quality import guard_empty_context
from docstruct.domain.models import SearchAnswer, SearchDocumentIndex, SearchSelectionDecision
from docstruct.domain.pageindex_search import (
    build_context_blocks,
    build_scope_clarification,
    choose_candidate_documents,
    fallback_node_matches,
)
from docstruct.infrastructure.logging import log_stage
from docstruct.infrastructure.metrics import Timer, get_metrics

if TYPE_CHECKING:
    from docstruct.application.ports import Neo4jRetrievalPort


class SearchGraphState(TypedDict, total=False):
    question: str
    indexes: List[SearchDocumentIndex]
    multi_document_intent: bool
    effective_question: str
    rewrite_note: Optional[str]
    inferred_document_ids: List[str]
    candidate_documents: List[SearchDocumentIndex]
    heuristic_clarification: Optional[str]
    selection: Optional[SearchSelectionDecision]
    selection_notes: Optional[str]
    selected_documents: List[SearchDocumentIndex]
    contexts: List[dict]
    retrieval_notes: List[str]
    final_answer: Optional[SearchAnswer]


class PageIndexSearchGraphRunner:
    def __init__(
        self,
        client,
        add_trace: Callable[..., None],
        summarize_documents: Callable[..., list[dict[str, str | None]]],
        neo4j_retrieval: Optional[Neo4jRetrievalPort] = None,
    ) -> None:
        self._agent = PageIndexSearchAgent(client)
        self._add_trace = add_trace
        self._summarize_documents = summarize_documents
        self._neo4j_retrieval = neo4j_retrieval
        self._graph = self._build_graph()

    def _neo4j_seed_node_ids(
        self,
        question: str,
        document_ids: list[str],
        *,
        limit: int = 8,
    ) -> dict[str, list[str]]:
        if self._neo4j_retrieval is None or not document_ids:
            return {}

        seed_nodes: dict[str, list[str]] = {}
        for candidate in self._neo4j_retrieval.retrieve_candidates(question, limit=max(limit, len(document_ids) * 2)):
            if candidate.document_id not in document_ids:
                continue
            candidate_seed_node_ids = list(candidate.source_node.get("seed_node_ids", []))
            if candidate.node_id and candidate.node_id not in candidate_seed_node_ids:
                candidate_seed_node_ids.insert(0, candidate.node_id)
            for node_id in candidate_seed_node_ids:
                if not node_id:
                    continue
                seed_nodes.setdefault(candidate.document_id, [])
                if node_id not in seed_nodes[candidate.document_id]:
                    seed_nodes[candidate.document_id].append(node_id)
        return seed_nodes

    @staticmethod
    def _promote_documents(
        documents: list[SearchDocumentIndex],
        preferred_ids: list[str],
        *,
        limit: int,
    ) -> list[SearchDocumentIndex]:
        by_id = {document.document_id: document for document in documents}
        ordered: list[SearchDocumentIndex] = []
        for document_id in preferred_ids:
            document = by_id.get(document_id)
            if document is not None and document not in ordered:
                ordered.append(document)
        for document in documents:
            if document not in ordered:
                ordered.append(document)
        return ordered[:limit]

    def _build_graph(self):
        graph = StateGraph(SearchGraphState)
        graph.add_node("rewrite_question", self._rewrite_question)
        graph.add_node("rank_candidates", self._rank_candidates)
        graph.add_node("select_documents", self._select_documents)
        graph.add_node("prepare_selected_documents", self._prepare_selected_documents)
        graph.add_node("retrieve_contexts", self._retrieve_contexts)
        graph.add_node("synthesize_answer", self._synthesize_answer)

        graph.add_edge(START, "rewrite_question")
        graph.add_edge("rewrite_question", "rank_candidates")
        graph.add_edge("rank_candidates", "select_documents")
        graph.add_conditional_edges(
            "select_documents",
            self._route_after_select_documents,
            {"prepare_selected_documents": "prepare_selected_documents", END: END},
        )
        graph.add_conditional_edges(
            "prepare_selected_documents",
            self._route_after_prepare_selected_documents,
            {"retrieve_contexts": "retrieve_contexts", END: END},
        )
        graph.add_conditional_edges(
            "retrieve_contexts",
            self._route_after_retrieve_contexts,
            {"synthesize_answer": "synthesize_answer", END: END},
        )
        graph.add_edge("synthesize_answer", END)
        return graph.compile()

    @staticmethod
    def _route_after_select_documents(state: SearchGraphState) -> str:
        return END if state.get("final_answer") is not None else "prepare_selected_documents"

    @staticmethod
    def _route_after_prepare_selected_documents(state: SearchGraphState) -> str:
        return END if state.get("final_answer") is not None else "retrieve_contexts"

    @staticmethod
    def _route_after_retrieve_contexts(state: SearchGraphState) -> str:
        return END if state.get("final_answer") is not None else "synthesize_answer"

    def run(
        self,
        *,
        question: str,
        indexes: list[SearchDocumentIndex],
        multi_document_intent: bool,
    ) -> SearchAnswer:
        state = self._graph.invoke(
            {
                "question": question,
                "indexes": indexes,
                "multi_document_intent": multi_document_intent,
                "effective_question": question,
                "rewrite_note": None,
                "inferred_document_ids": [],
                "candidate_documents": [],
                "heuristic_clarification": None,
                "selection": None,
                "selection_notes": None,
                "selected_documents": [],
                "contexts": [],
                "retrieval_notes": [],
                "final_answer": None,
            }
        )
        final_answer = state.get("final_answer")
        if final_answer is None:
            raise ValueError("The search graph did not produce an answer.")
        return final_answer

    def _rewrite_question(self, state: SearchGraphState) -> SearchGraphState:
        question = state["question"]
        indexes = state["indexes"]
        effective_question = question
        rewrite_note = None
        inferred_document_ids: list[str] = []
        try:
            effective_question, rewrite_note, inferred_document_ids = self._agent.rewrite_question(question, indexes)
            self._add_trace(
                "rewrite_question",
                "Rewrote the question for retrieval.",
                original_question=question,
                rewritten_question=effective_question,
                reasoning=rewrite_note,
                inferred_document_ids=inferred_document_ids,
            )
        except Exception:
            self._add_trace(
                "rewrite_question",
                "Question rewrite failed, so the original question will be used.",
                original_question=question,
            )
        if effective_question != question:
            rewrite_note = " | ".join(
                note
                for note in [
                    f"Rewrote question for retrieval: {effective_question}",
                    rewrite_note,
                ]
                if note
            )
        return {
            "effective_question": effective_question,
            "rewrite_note": rewrite_note,
            "inferred_document_ids": inferred_document_ids,
            "retrieval_notes": [note for note in [rewrite_note] if note],
        }

    def _rank_candidates(self, state: SearchGraphState) -> SearchGraphState:
        effective_question = state["effective_question"]

        # Use Neo4j retrieval if available, otherwise fall back to in-memory method
        if self._neo4j_retrieval:
            # Retrieve candidates from Neo4j
            retrieval_candidates = self._neo4j_retrieval.retrieve_candidates(
                question=effective_question,
                query_embedding=None,  # Vector mode not enabled by default
                limit=6,
            )

            # Convert RetrievalCandidate objects to SearchDocumentIndex objects
            candidate_documents: list[SearchDocumentIndex] = []
            for candidate in retrieval_candidates:
                doc_index = self._neo4j_retrieval.get_document_index(candidate.document_id)
                if doc_index:
                    candidate_documents.append(doc_index)
        else:
            # Fall back to in-memory candidate selection (original behavior)
            candidate_documents = choose_candidate_documents(effective_question, state["indexes"], limit=6)

        inferred_document_ids = state.get("inferred_document_ids", [])
        if inferred_document_ids:
            candidate_documents = self._promote_documents(candidate_documents, inferred_document_ids, limit=6)
        self._add_trace(
            "candidate_ranking",
            "Ranked candidate documents for the effective retrieval question.",
            effective_question=effective_question,
            candidates=self._summarize_documents(candidate_documents, limit=6),
            retrieval_backend="neo4j" if self._neo4j_retrieval is not None else "pageindex",
        )
        heuristic_clarification = build_scope_clarification(effective_question, candidate_documents[:4])
        return {
            "candidate_documents": candidate_documents,
            "heuristic_clarification": heuristic_clarification,
        }

    def _select_documents(self, state: SearchGraphState) -> SearchGraphState:
        effective_question = state["effective_question"]
        candidate_documents = state["candidate_documents"]
        heuristic_clarification = state.get("heuristic_clarification")
        rewrite_note = state.get("rewrite_note")
        try:
            selection = self._agent.select_documents(effective_question, candidate_documents)
            self._add_trace(
                "document_selection",
                "Selected document scopes for answer generation.",
                effective_question=effective_question,
                selected_document_ids=selection.document_ids,
                needs_clarification=selection.needs_clarification,
                clarifying_question=selection.clarifying_question,
                reasoning=selection.thinking,
            )
        except Exception:
            selection = None
            self._add_trace(
                "document_selection",
                "Document selection failed, so the workflow will fall back to heuristic candidates.",
                effective_question=effective_question,
            )

        if selection and selection.needs_clarification:
            clarifying_question = selection.clarifying_question or heuristic_clarification
            return {
                "selection": selection,
                "selection_notes": selection.thinking,
                "final_answer": SearchAnswer(
                    question=state["question"],
                    answer=clarifying_question or "I need the university, region, or issuing organization before I can answer safely.",
                    document_ids=[],
                    retrieval_notes=" | ".join(note for note in [rewrite_note, selection.thinking] if note) or None,
                    needs_clarification=True,
                    clarifying_question=clarifying_question,
                ),
            }

        return {
            "selection": selection,
            "selection_notes": selection.thinking if selection else None,
        }

    def _prepare_selected_documents(self, state: SearchGraphState) -> SearchGraphState:
        candidate_documents = state["candidate_documents"]
        selection = state.get("selection")
        inferred_document_ids = state.get("inferred_document_ids", [])
        heuristic_clarification = state.get("heuristic_clarification")
        rewrite_note = state.get("rewrite_note")
        selection_notes = state.get("selection_notes")
        question = state["question"]
        effective_question = state["effective_question"]
        multi_document_intent = state["multi_document_intent"]

        selected_document_ids = selection.document_ids if selection else []
        document_map = {document.document_id: document for document in candidate_documents}
        selected_documents = [
            document_map[document_id]
            for document_id in selected_document_ids
            if document_id in document_map
        ]
        if multi_document_intent and len(selected_documents) < 2:
            selected_documents = self._promote_documents(candidate_documents, selected_document_ids, limit=min(4, len(candidate_documents)))
        if not selected_documents:
            if inferred_document_ids:
                selected_documents = [
                    document_map[document_id]
                    for document_id in inferred_document_ids
                    if document_id in document_map
                ]
            if heuristic_clarification:
                self._add_trace(
                    "clarification_gate",
                    "Requested clarification after candidate ranking because multiple scopes still match.",
                    selected_documents=self._summarize_documents(candidate_documents[:4]),
                    clarifying_question=heuristic_clarification,
                )
                return {
                    "final_answer": SearchAnswer(
                        question=question,
                        answer=heuristic_clarification,
                        document_ids=[],
                        retrieval_notes=" | ".join(note for note in [rewrite_note, selection_notes] if note) or None,
                        needs_clarification=True,
                        clarifying_question=heuristic_clarification,
                    )
                }
            if not selected_documents:
                selected_documents = candidate_documents[: min(3, len(candidate_documents))]

        self._add_trace(
            "selected_documents",
            "Prepared the final document set for node retrieval.",
            selected_documents=self._summarize_documents(selected_documents, limit=6),
        )

        post_selection_clarification = None if multi_document_intent else build_scope_clarification(effective_question, selected_documents)
        if post_selection_clarification:
            self._add_trace(
                "clarification_gate",
                "Requested clarification because the selected documents still span multiple scopes.",
                selected_documents=self._summarize_documents(selected_documents, limit=6),
                clarifying_question=post_selection_clarification,
            )
            return {
                "final_answer": SearchAnswer(
                    question=question,
                    answer=post_selection_clarification,
                    document_ids=[document.document_id for document in selected_documents],
                    retrieval_notes=" | ".join(note for note in [rewrite_note, selection_notes] if note) or None,
                    needs_clarification=True,
                    clarifying_question=post_selection_clarification,
                )
            }

        return {"selected_documents": selected_documents}

    def _retrieve_contexts(self, state: SearchGraphState) -> SearchGraphState:
        effective_question = state["effective_question"]
        selected_documents = state["selected_documents"]
        contexts: list[dict] = []
        retrieval_notes = list(state.get("retrieval_notes", []))
        seed_nodes_by_document = self._neo4j_seed_node_ids(
            effective_question,
            [document.document_id for document in selected_documents],
        )

        # Dynamic context sizing
        context_config = ContextConfig.from_env()
        total_node_count = 0

        for document in selected_documents:
            preferred_node_ids = list(seed_nodes_by_document.get(document.document_id, []))
            try:
                with log_stage("node_selection", document_id=document.document_id):
                    node_ids, node_notes = self._agent.select_nodes(effective_question, document)
                    get_metrics().record_llm_call()
                self._add_trace(
                    "node_selection",
                    "Selected nodes from the document tree.",
                    document_id=document.document_id,
                    node_ids=node_ids,
                    reasoning=node_notes,
                )
            except Exception:
                node_ids, node_notes = [], None
                self._add_trace(
                    "node_selection",
                    "Node selection failed, so heuristic node matching will be used.",
                    document_id=document.document_id,
                )
            if preferred_node_ids:
                node_ids = [*preferred_node_ids, *node_ids]
                deduped_node_ids: list[str] = []
                for node_id in node_ids:
                    if node_id and node_id not in deduped_node_ids:
                        deduped_node_ids.append(node_id)
                node_ids = deduped_node_ids[:6]
                self._add_trace(
                    "neo4j_seed_nodes",
                    "Promoted Neo4j section hits into the node-selection stage.",
                    document_id=document.document_id,
                    node_ids=node_ids,
                )
            if not node_ids:
                node_ids = fallback_node_matches(effective_question, document, limit=4)
                self._add_trace(
                    "fallback_nodes",
                    "Used heuristic node matching because no node ids were returned.",
                    document_id=document.document_id,
                    node_ids=node_ids,
                )
            total_node_count += len(node_ids)
            if node_notes:
                retrieval_notes.append(f"{document.document_id}: {node_notes}")

            # Use dynamic context sizing
            effective_max_chars = context_config.effective_max_chars(total_node_count)
            contexts.extend(build_context_blocks(
                document, node_ids, question=effective_question, max_chars=effective_max_chars,
            ))

        # Empty context guard
        empty_guard_msg = guard_empty_context(contexts)
        if empty_guard_msg is not None:
            self._add_trace(
                "context_building",
                "Empty context guard triggered.",
                message=empty_guard_msg,
            )
            return {
                "contexts": [],
                "retrieval_notes": retrieval_notes,
                "final_answer": SearchAnswer(
                    question=state["question"],
                    answer=empty_guard_msg,
                    document_ids=[document.document_id for document in selected_documents],
                    retrieval_notes=" | ".join(retrieval_notes) if retrieval_notes else None,
                ),
            }

        # Trim to max blocks
        contexts = contexts[:context_config.max_context_blocks]

        self._add_trace(
            "context_building",
            "Built grounded context snippets for answer synthesis.",
            context_count=len(contexts),
            document_ids=[document.document_id for document in selected_documents],
        )
        return {
            "contexts": contexts,
            "retrieval_notes": retrieval_notes,
        }

    def _synthesize_answer(self, state: SearchGraphState) -> SearchGraphState:
        selected_documents = state["selected_documents"]
        contexts = state["contexts"]
        retrieval_note_text = " | ".join(note for note in state.get("retrieval_notes", []) if note) or None
        timer = Timer().start()
        try:
            with log_stage("answer_synthesis"):
                answer = self._agent.answer_from_contexts(
                    state["question"],
                    contexts[:8],
                    document_ids=[document.document_id for document in selected_documents],
                    retrieval_notes=retrieval_note_text,
                    retrieval_backend="neo4j" if self._neo4j_retrieval is not None else "pageindex",
                )
                get_metrics().record_llm_call()
            get_metrics().record_stage("answer_synthesis", timer.stop())
            self._add_trace(
                "answer_synthesis",
                "Synthesized the final grounded answer from the selected contexts.",
                answer_preview=answer.answer[:240],
                citation_count=len(answer.citations),
                needs_clarification=answer.needs_clarification,
            )
            return {"final_answer": answer}
        except Exception:
            get_metrics().record_stage("answer_synthesis", timer.stop(), error=True)
            fallback_answer = " ".join(context["text"] for context in contexts[:2] if context.get("text")).strip()
            if not fallback_answer:
                fallback_answer = "I found relevant document nodes, but I could not synthesize a grounded answer."
            self._add_trace(
                "answer_synthesis",
                "Fell back to raw context because final answer synthesis failed.",
                answer_preview=fallback_answer[:240],
            )
            return {
                "final_answer": SearchAnswer(
                    question=state["question"],
                    answer=fallback_answer,
                    document_ids=[document.document_id for document in selected_documents],
                    retrieval_notes=retrieval_note_text,
                )
            }
