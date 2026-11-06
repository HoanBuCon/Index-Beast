"""LangGraph request preparation; clients stay outside invocation state/checkpoints.

Phụ trách: TV3 · [S2–S3] Pipeline
"""

import asyncio
import inspect
import json
import re
import time
import unicodedata
from datetime import UTC, datetime
from typing import TypedDict
from urllib.parse import urlsplit
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.messages import convert_to_openai_messages
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.adapters.tavily import WebHit, WebSearchError
from app.api.schemas.chat import ChatRequest, Clarification
from app.rag.agent import decide, spend
from app.rag.context_policy import coverage_order
from app.rag.evidence import evidence_units
from app.rag.generator import LLM, Generator, Prepared
from app.rag.history import dependent, select_history
from app.rag.overview import Overview, detect_overview, no_overview_evidence, overview_queries, prefer_overview
from app.rag.prompts import generation_prompt, prompt
from app.rag.query_plan import content_key, fuse_ranked, plan_queries
from app.rag.reranker import NoReranker, Reranker
from app.rag.retriever import document_to_hit, hit_to_document
from app.rag.rewrite import contextual_followup, rewrite
from app.rag.web_query import web_query
from app.rag.web_search import assess, merge_evidence
from core.config import Settings
from core.corpus import CorpusPolicy
from core.errors import AppError, BadRequestError, UnavailableError, UpstreamError
from core.types import Hit


class PreparationState(TypedDict, total=False):
    req: ChatRequest
    history: list[dict]
    selected_memories: list[dict]
    original_question: str
    resolved_question: str
    query: str  # Retrieval query; never used to change the answer language.
    answer_language: str
    started: float
    prepared: Prepared
    diagnostic_queries: bool
    gameplay: bool
    handle_gameplay: bool
    player: object
    next_player: object
    documents: list[Document]
    web_hits: list[WebHit]
    entities: list[str]
    overview: Overview | None
    search_mode: str
    assessment_status: str | None
    needs_web: bool
    local: list[Hit]
    local_context: list[dict]
    memory_scope: object
    memory_candidates: list[dict]


def language(question: str, requested: str) -> str:
    if requested != "auto":
        return requested
    normalized = unicodedata.normalize("NFD", question.lower())
    if (
        any(unicodedata.combining(c) for c in normalized)
        or "đ" in question.lower()
        or re.search(r"\b(la ai|tai sao|cho toi|nhan vat|cot truyen|o dau|chao|cam on)\b", question.lower())
    ):
        return "vi"
    return "en"


def outside_scope(question: str) -> bool:
    plain = "".join(c for c in unicodedata.normalize("NFD", question.lower()) if not unicodedata.combining(c))
    return bool(
        re.search(
            r"\b(dark souls|bitcoin|fibonacci|cover letter|"
            r"gaming laptop|python code|viet.*chuong trinh|"
            r"(?:ignore|disregard|forget) (?:all |the |your )?(?:previous |prior |system )?(?:instructions|rules)|"
            r"(?:reveal|print|show) (?:your |the )?(?:system prompt|api key)|"
            r"bo qua (?:tat ca )?(?:huong dan|chi dan|quy tac)|tiet lo (?:system prompt|api key))\b",
            plain,
        )
    )


_SMALL_TALK = (
    (
        re.compile(
            r"(?:xin )?chao(?: ban| cau| em| anh| chi)?|hi|hello|hey|good (?:morning|afternoon|evening)|"
            r"(?:ban|cau|em) (?:la ai|la gi|ten gi|ten la gi)|who are you|what are you|what(?: is|'s) your name"
        ),
        {
            "vi": "Chào bạn! Mình là IndexBeast, trợ lý Elden Ring của nhóm 4 Hollows. "
            "Bạn muốn tìm hiểu cốt truyện, nhiệm vụ, trang bị, boss hay build?",
            "en": "Hi! I'm IndexBeast, the Elden Ring assistant from team 4 Hollows. "
            "Would you like to explore lore, quests, equipment, bosses or builds?",
        },
    ),
    (
        re.compile(r"(?:xin )?cam on(?: ban| nhe| nha)?|thanks?(?: you)?|thx"),
        {
            "vi": "Không có gì! Bạn cần tìm hiểu thêm gì về Elden Ring cứ hỏi nhé.",
            "en": "You're welcome! Ask away if you want to know more about Elden Ring.",
        },
    ),
)


def small_talk(question: str, lang: str) -> str | None:
    """Whole-message greetings/identity/thanks only; anything longer stays a game question."""
    plain = "".join(c for c in unicodedata.normalize("NFD", question.lower()) if not unicodedata.combining(c))
    text = " ".join(re.sub(r"[^\w\s']", " ", plain).split())
    return next((replies[lang] for pattern, replies in _SMALL_TALK if pattern.fullmatch(text)), None)


def unresolved_reference(question: str) -> bool:
    """Conservative pronoun-leading gate, not NER. A named/content prefix is left to the LLM/rewrite."""
    pronoun = re.search(r"\b(ông ta|cô ấy|anh ấy|nó|họ|he|she|him|her|it|they|them)\b", question, re.I)
    if pronoun is None:
        return False
    words = re.findall(r"[^\W\d_]+", question[: pronoun.start()].lower())
    question_words = set(
        [
            "who",
            "what",
            "why",
            "where",
            "when",
            "how",
            "which",
            "is",
            "are",
            "was",
            "were",
            "does",
            "did",
            "do",
            "can",
            "could",
            "would",
            "should",
            "will",
            "tell",
            "me",
            "i",
            "get",
            "obtain",
            "find",
            "us",
            "about",
            "explain",
            "describe",
            "please",
            "the",
            "a",
            "an",
            "of",
            "to",
            "for",
            "and",
            "you",
            "your",
            "happened",
            "happen",
            "tại",
            "sao",
            "vì",
            "ai",
            "là",
            "ở",
            "đâu",
            "khi",
            "nào",
            "hãy",
            "cho",
            "tôi",
            "biết",
            "giải",
            "thích",
            "về",
            "và",
            "lấy",
            "tìm",
            "nhặt",
            "kiếm",
            "đã",
            "có",
            "thể",
        ]
    )
    return all(word in question_words for word in words)


def select_context(
    hits: list[Hit],
    limit: int,
    budget: int,
    *,
    policy: CorpusPolicy | None = None,
    spoilers: bool = True,
    entities: list[str] | None = None,
    query: str = "",
) -> list[Hit]:
    admission = policy or CorpusPolicy()
    selected, seen, seen_content, used = [], set(), set(), 0
    eligible = []
    for hit in hits:
        p = hit.payload
        if (not isinstance(hit, WebHit) and admission.exclusion_reason(p, spoilers=spoilers)) or (
            isinstance(hit, WebHit) and not spoilers
        ):
            continue
        if not all(isinstance(p.get(k), str) and p[k].strip() for k in ("text", "title", "url")):
            continue
        if urlsplit(p["url"]).scheme not in {"https", "http"} or not urlsplit(p["url"]).netloc:
            continue
        eligible.append(hit)
    for hit in coverage_order(eligible, entities or [], query):
        key = content_key(hit)
        if hit.id in seen or (key is not None and key in seen_content):
            continue
        size = len(json.dumps(context_item(hit, len(selected) + 1), ensure_ascii=False)) + 2
        if used + size > budget:
            continue  # Whole chunks only: do not silently cut dialogue/conditions.
        selected.append(hit)
        seen.add(hit.id)
        if key is not None:
            seen_content.add(key)
        used += size
        if len(selected) >= limit:
            break
    return selected


def context_item(hit: Hit, index: int) -> dict:
    p = hit.payload
    item = {
        "index": index,
        "point_id": hit.id,
        "chunk_id": p.get("artifact_chunk_id", p.get("chunk_id", hit.id)),
        "title": p["title"],
        "section": p.get("section"),
        "source_type": p["source_type"],
        "origin": "web" if isinstance(hit, WebHit) else "corpus",
        "text": p["text"],
    }
    # Preserve provided unknown/null values, without fabricating absent metadata or wasting budget on it.
    for key in (
        "source_type_evidence",
        "source",
        "lang",
        "game_scope",
        "release_scope",
        "continuity",
        "review_status",
        "game_version",
        "patch_version",
        "upgrade_level",
        "affinity",
        "ng_cycle",
        "source_updated_at",
        "trigger",
        "speaker",
        "variant_context",
        "unit_kind",
        "retrieved_at",
        "local_candidate_origin",
        "rule_kind",
    ):
        if key in p:
            item[key] = p[key]
    if "indexbeast_admission" in p:
        item["admission_policy"] = p["indexbeast_admission"]
    units = evidence_units(p["text"])
    item["evidence_units"] = {"q0": "entire source text above"} if "q0" in units else units
    return item


class ChatPipeline:
    def __init__(
        self,
        settings: Settings,
        llm: LLM | None,
        retriever: BaseRetriever | None = None,
        reranker: Reranker | None = None,
        web_search=None,
        memory=None,
    ):
        self.settings, self.llm, self.retriever = settings, llm, retriever
        self.web_search = web_search
        self.memory = memory
        self.policy = CorpusPolicy.from_settings(settings)
        store = getattr(retriever, "store", None)
        if store is not None and store.policy != self.policy:
            raise ValueError("Retriever and pipeline must use the same corpus policy/languages")
        self.reranker = (reranker or NoReranker()) if settings.chat_mode == "rag" else None
        self.generator = (
            Generator(llm, thinking=settings.rag_thinking_enabled, format_retries=settings.rag_format_retries)
            if llm is not None
            else None
        )
        self.template = generation_prompt()
        graph = StateGraph(PreparationState)
        for name, node in (
            ("scope", self._scope),
            ("gameplay", self._gameplay),
            ("memory", self._memory),
            ("agent_decision", self._agent),
            ("rewrite", self._rewrite),
            ("retrieve", self._retrieve),
            ("rerank", self._rerank),
            ("assess", self._assess),
            ("web", self._search_web),
            ("context", self._context),
            ("prompt", self._prompt_node),
        ):
            graph.add_node(name, self._guarded(name, node))
        graph.add_edge(START, "scope")
        graph.add_conditional_edges("scope", lambda s: self._agent_active(s), {True: "memory", False: "gameplay"})
        graph.add_edge("gameplay", "memory")
        graph.add_conditional_edges(
            "memory",
            lambda s: "agent" if self._agent_active(s) else self._rag_route(s),
            {"agent": "agent_decision", "rag": "rewrite", "answer": "prompt"},
        )
        graph.add_conditional_edges("agent_decision", self._rag_route, {"rag": "rewrite", "answer": "prompt"})
        graph.add_conditional_edges("rewrite", self._rag_route, {"rag": "retrieve", "answer": "prompt"})
        graph.add_edge("retrieve", "rerank")
        graph.add_edge("rerank", "assess")
        graph.add_conditional_edges("assess", lambda s: s["needs_web"], {True: "web", False: "context"})
        graph.add_edge("web", "context")
        graph.add_edge("context", "prompt")
        graph.add_edge("prompt", END)
        # Invocation-local state, overwrite semantics, no MessagesState/append reducer or shared checkpointer.
        self.prepare_graph = graph.compile(name="indexbeast_prepare")

    @staticmethod
    def _guarded(name, node):
        async def run(state: PreparationState):
            try:
                result = node(state)
                if inspect.isawaitable(result):
                    result = await result
                state["prepared"].trace.setdefault("graph_nodes", []).append(name)
                return result
            except AppError as exc:
                if state.get("diagnostic_queries") and "prepared" in state:
                    exc.rag_diagnostics = dict(state["prepared"].trace)
                raise

        return run

    async def prepare(
        self,
        req,
        history: list[dict],
        *,
        diagnostic_queries: bool = False,
        gameplay: bool = False,
        handle_gameplay: bool = False,
        player=None,
        memory_scope=None,
    ) -> Prepared:
        state = {
            "req": req,
            "history": history,
            "started": time.perf_counter(),
            "diagnostic_queries": diagnostic_queries,
            "gameplay": gameplay,
            "handle_gameplay": handle_gameplay,
            "player": player,
            "memory_scope": memory_scope,
            "original_question": req.message,
            "resolved_question": req.message,
        }
        with tracing_context(enabled=False):
            result = await self.prepare_graph.ainvoke(state, config={"recursion_limit": 24})
            return result["prepared"]

    def _scope(self, state: dict) -> dict:
        req = state["req"]
        if self.llm is None:
            raise UnavailableError("Chưa cấu hình DeepSeek API key.")
        mode = self.settings.chat_mode
        lang = language(req.message, req.options.lang)
        prepared = Prepared(mode, lang, [], trace={"mode": mode, "rewrite_fallback": False})
        state.update(prepared=prepared, query=req.message, documents=[], answer_language=lang)
        requested = "auto" if req.channel == "discord" else (req.options.web_search or self.settings.web_search_mode)
        state["search_mode"] = requested if self.settings.web_search_available else "off"
        prepared.trace["web_search"] = {"requested": requested, "mode": state["search_mode"], "status": "not_run"}
        if self._agent_active(state):
            prepared.max_calls = self.settings.chat_agent_max_calls
            return state
        if outside_scope(req.message):
            prepared.static_answer = (
                "Mình có thể giúp bạn về Elden Ring: cốt truyện, nhiệm vụ, trang bị, cơ chế và hướng build. "
                "Bạn muốn tìm hiểu phần nào trong game?"
                if lang == "vi"
                else "I can help with Elden Ring lore, quests, equipment, mechanics and build ideas. "
                "What would you like to explore in the game?"
            )
        elif reply := small_talk(req.message, lang):
            # Không cần bằng chứng nên không gọi rewrite/retrieval; rewrite sẽ coi đây là out_of_scope.
            prepared.static_answer = reply
        if mode == "rag" and prepared.static_answer is None and self.settings.rag_overview_enabled:
            state["overview"] = detect_overview(req.message)
            if state["overview"] is not None:
                prepared.trace["request_kind"] = "overview"
                prepared.trace["overview_topic"] = state["overview"].topic
        return state

    @staticmethod
    def _rag_route(state: PreparationState) -> str:
        p = state["prepared"]
        return "rag" if p.mode == "rag" and p.static_answer is None else "answer"

    def _agent_active(self, state):
        return self.settings.chat_agent_enabled and state["prepared"].mode == "rag"

    async def _agent(self, state):
        p, req = state["prepared"], state["req"]
        working = state.get("player") if isinstance(state.get("player"), dict) else {}
        shared_thread = req.channel == "discord" and (req.external_ref or "").startswith("discord:thread:")
        if shared_thread:
            working = {}  # No verified actor identity in the shared-thread transport.
        if time.time() - working.get("updated", 0) > 1800:
            working = {}
        pending = working.get("pending")
        if pending and datetime.fromisoformat(pending["expires_at"]).timestamp() <= time.time():
            working = {}
            pending = None
        if req.clarification_id and (not pending or str(req.clarification_id) != pending["id"]):
            raise BadRequestError("Câu hỏi bổ sung đã hết hạn hoặc không thuộc hội thoại này.")
        decision = await decide(
            self.llm,
            req.message,
            state.get("memory_candidates", []),
            working,
            p.lang,
            self.settings,
            p.trace,
            shared_thread=shared_thread,
            requested_lang=req.options.lang,
        )
        if decision is None:
            raise UpstreamError("Mô hình chưa trả quyết định hợp lệ. Vui lòng thử lại.")
        p.agent_decision = decision.model_dump()
        if req.options.lang == "auto" and decision.answer_language:
            p.lang = state["answer_language"] = decision.answer_language
        continuing = decision.turn_type != "new" and decision.intent != "cancel"
        rounds = working.get("clarification_rounds", 0) if continuing else 0
        if decision.action == "clarify" and rounds >= 3:
            raise UnavailableError(
                "Đã đạt giới hạn hỏi bổ sung. Bạn có thể gửi yêu cầu cụ thể hơn hoặc hủy yêu cầu này."
            )
        p.player_state = {
            "constraints": [c.model_dump() for c in decision.constraints],
            "original": working.get("original", req.message) if continuing else req.message,
            "request_text": working.get("request_text", req.message) if continuing else req.message,
            "clarification_rounds": rounds + 1 if decision.action == "clarify" else 0,
            "intent": decision.intent,
            "lang": p.lang,
            "pending": None,
            "updated": time.time(),
        }
        state["next_player"] = p.player_state
        if decision.intent == "cancel":
            p.player_state = state["next_player"] = {"updated": time.time(), "constraints": [], "pending": None}
        state["history"] = []
        state["entities"] = decision.entities
        state["query"] = decision.search_query if decision.rewrite else req.message
        state["resolved_question"] = decision.resolved_question or req.message
        state["gameplay"] = decision.intent in {"build", "route", "quest", "mechanics", "acquisition"}
        p.trace["rewrite"] = {
            "status": "accepted" if decision.rewrite else "not_run",
            "reason": "agent_decision",
            "model_calls": 0,
        }
        p.trace["memory"]["selected_ids"] = decision.selected_memory_ids
        if decision.action == "clarify":
            clarification = Clarification(
                id=uuid4(),
                question=decision.reply,
                fields=decision.missing,
                expires_at=datetime.fromtimestamp(time.time() + 1800, UTC).isoformat(),
            )
            p.clarification = clarification
            p.player_state["pending"] = clarification.model_dump(mode="json")
        if decision.action != "retrieve":
            p.static_answer = decision.reply
        return state

    def _gameplay(self, state: PreparationState) -> dict:
        from app.services.gameplay import PlayerState, advance

        p = state["prepared"]
        if not state.get("handle_gameplay") or self._rag_route(state) != "rag":
            return state
        decision = advance(state.get("player") or PlayerState(), state["req"], p.lang)
        state["next_player"] = decision.state
        p.player_state = decision.state
        p.trace["gameplay"] = {"status": decision.status, "confirmed_slots": dict(decision.state.slots)}
        if decision.reply:
            p.static_answer, p.clarification = decision.reply, decision.clarification
            p.trace["gameplay"]["tool_calls"] = 0
        else:
            state["req"] = state["req"].model_copy(update={"message": decision.query})
            state["query"] = state["resolved_question"] = decision.query
            # The resolved request already carries confirmed working state; do not search old topics.
            if decision.status == "resumed" and state["req"].options.lang == "auto":
                p.lang = decision.state.lang
                state["answer_language"] = p.lang
            state["overview"] = detect_overview(decision.query) if self.settings.rag_overview_enabled else None
        return state

    async def _memory(self, state: PreparationState) -> dict:
        p = state["prepared"]
        if self._agent_active(state):
            if not self.settings.chat_history_messages or not self.settings.chat_history_chars:
                rows, diagnostic = [], {"method": "disabled", "status": "disabled"}
            elif self.memory is not None and state.get("memory_scope") is not None:
                rows, diagnostic = await self.memory.recall(state["memory_scope"], state["req"].message)
            else:
                # Legacy RAM mode has no claim of durable/semantic memory. Supply only two user anchors.
                users = [r for r in state["history"] if r.get("role") == "user"][-2:]
                rows = [
                    {
                        "id": r.get("message_id", str(i)),
                        "source_id": r.get("message_id", str(i)),
                        "text": r["content"],
                        "kind": "topic",
                        "recent": True,
                    }
                    for i, r in enumerate(users)
                ]
                diagnostic = {"method": "ram_recent", "status": "limited", "candidates": len(rows)}
            # Candidate count and chars are budgets, not semantic relevance decisions.
            bounded, used = [], 0
            for row in rows[: self.settings.chat_history_messages]:
                if used + len(row["text"]) <= self.settings.chat_history_chars:
                    bounded.append(row)
                    used += len(row["text"])
            rows = bounded
            if state["req"].channel == "discord" and (state["req"].external_ref or "").startswith("discord:thread:"):
                rows = [row for row in rows if row.get("kind") != "fact"]
            state["memory_candidates"] = rows
            state["history"] = []
            p.trace["memory"] = diagnostic
            return state
        if p.static_answer is not None:
            state["history"] = []
            return state
        if state.get("overview") is not None:
            state["history"] = state["selected_memories"] = []
            p.trace["memory"] = {"method": "lexical_user_turns", "reason": "standalone_overview", "selected": 0}
            return state
        selection = select_history(
            state["query"],
            state["history"],
            max_messages=self.settings.chat_history_messages,
            max_chars=self.settings.chat_history_chars,
        )
        state["history"] = selection.rows
        state["selected_memories"] = selection.rows
        p.trace["memory"] = {
            "method": "lexical_user_turns",
            "reason": selection.reason,
            "selected": len(selection.rows),
            "provenance": selection.provenance,
        }
        if selection.ambiguous:
            p.static_answer = (
                "Bạn muốn nói tiếp về nhân vật, trang bị hoặc chủ đề nào trong Elden Ring?"
                if p.lang == "vi"
                else "Which Elden Ring character, equipment or topic would you like to continue?"
            )
        return state

    def _prompt_node(self, state: PreparationState) -> dict:
        return {"prepared": self._prompt(state)}

    async def _rewrite(self, state: dict) -> dict:
        p = state["prepared"]
        # A clarification does not need a configured web provider. Check forced-search
        # availability only after working state/memory have resolved or asked the user.
        if p.trace["web_search"]["requested"] == "always" and not self.settings.web_search_available:
            raise UnavailableError("Tìm trên web hiện chưa khả dụng. Chọn chế độ tự động hoặc thử lại sau.")
        if self._agent_active(state):
            return state  # Decision model already chose and validated rewrite in the same call.
        if state.get("overview") is not None:
            # A recognized global topic is already a valid scope, not an ambiguous referent.
            # The bounded overview query plan supplies English search cues without a paid rewrite call.
            p.trace["rewrite"] = {"status": "not_run", "reason": "overview_query_plan", "model_calls": 0}
            return state
        if self.settings.rag_rewrite_enabled or state.get("search_mode", "off") != "off" or state["history"]:
            diagnostics = {}
            rewritten, fallback = await rewrite(
                self.llm,
                state["query"],
                state["history"],
                p.lang,
                deadline_seconds=min(self.settings.rag_rewrite_timeout_seconds, 4)
                if state.get("search_mode", "off") != "off"
                else self.settings.rag_rewrite_timeout_seconds,
                max_tokens=self.settings.rag_rewrite_max_tokens,
                diagnostics=diagnostics,
            )
            p.trace["rewrite"] = diagnostics
            p.trace["rewrite_fallback"] = fallback
            if rewritten.out_of_scope:
                p.static_answer = (
                    "Câu này nằm ngoài Elden Ring nên mình không giúp được. "
                    "Bạn muốn hỏi về cốt truyện, nhiệm vụ, trang bị, boss hay build?"
                    if p.lang == "vi"
                    else "That's outside Elden Ring, so I can't help with it. "
                    "Would you like to ask about lore, quests, equipment, bosses or builds?"
                )
            elif (
                rewritten.ambiguous
                or (state["history"] and not rewritten.entities)
                or (
                    fallback
                    and (dependent(state["query"]) or (not state["history"] and unresolved_reference(state["query"])))
                )
            ):
                p.static_answer = (
                    "Bạn đang hỏi nhân vật, trang bị, boss hoặc nhiệm vụ nào trong Elden Ring?"
                    if p.lang == "vi"
                    else "Which Elden Ring character, equipment, boss or quest do you mean?"
                )
            else:
                state["query"] = rewritten.standalone_query_en
                state["entities"] = rewritten.entities
                if state["history"]:
                    state["resolved_question"] = rewritten.standalone_query_en
        elif contextual_followup(state["query"]) or (not state["history"] and unresolved_reference(state["query"])):
            p.static_answer = "Bạn đang hỏi nhân vật nào?" if p.lang == "vi" else "Which character do you mean?"
        return state

    async def _retrieve(self, state: dict) -> dict:
        if state["prepared"].static_answer is None:
            if self.retriever is None:
                raise UnavailableError("Kho tri thức RAG chưa được cấu hình.")
            # Copy only the Pydantic retriever wrapper; clients/encoder remain shared.
            retriever = self.retriever.model_copy(
                update={
                    "spoilers": state["req"].options.spoilers,
                    "limit": self.settings.rag_prefetch,
                }
            )
            original = state.get("resolved_question", state["req"].message)
            if state["prepared"].agent_decision.get("turn_type") == "new":
                original = state["req"].message
            queries = plan_queries(original, state["query"], self.settings.rag_query_mode)
            if state.get("overview") is not None:
                queries = overview_queries(queries, state["overview"])
            rows, diagnostics = [], []
            for kind, query in queries:
                started = time.perf_counter()
                row = {"kind": kind}
                if state.get("diagnostic_queries"):
                    row["query"] = query
                try:
                    timeout = self.settings.rag_retrieval_timeout_seconds
                    if state.get("search_mode", "off") != "off":
                        timeout = min(timeout, 5)
                    async with asyncio.timeout(timeout / len(queries)):
                        documents = await retriever.ainvoke(query)
                    hits = [document_to_hit(d) for d in documents[: self.settings.rag_prefetch]]
                    rows.append(hits)
                    row.update(status="ok", candidates=len(hits))
                except (UnavailableError, TimeoutError) as exc:
                    row.update(status="error", error_type=type(exc).__name__)
                row["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
                diagnostics.append(row)
            p = state["prepared"]
            p.trace["retrieval_queries"] = diagnostics
            if not rows:
                raise UnavailableError("Không thể truy vấn kho tri thức RAG.")
            # One query keeps its native Qdrant score. Dual-query scores are rank fusion, NOT probabilities.
            hits = rows[0] if len(rows) == 1 else fuse_ranked(rows, self.settings.rag_prefetch)
            state["documents"] = [hit_to_document(h) for h in hits]
            p.trace["retrieved"] = [
                {
                    "id": h.id,
                    "score": h.score,
                    "chunk_id": h.payload.get("artifact_chunk_id", h.id),
                    "title": h.payload.get("title"),
                    "url": h.payload.get("url"),
                }
                for h in hits
            ]
        return state

    async def _rerank(self, state: dict) -> dict:
        if state["prepared"].static_answer is None:
            hits = [document_to_hit(d) for d in state["documents"]]
            ranked = await self.reranker.rank(state["query"], hits)
            if self.settings.gameplay_knowledge_enabled and state.get("gameplay"):
                from app.rag.gameplay_knowledge import supplements

                extra = await asyncio.to_thread(
                    supplements,
                    state.get("resolved_question", state["req"].message) + "\n" + state["req"].message,
                    self.policy,
                    state["req"].options.spoilers,
                )
                if extra:
                    ids = {h.id for h in extra}
                    ranked = [*extra, *(h for h in ranked if h.id not in ids)]
                    state["prepared"].trace["curated_supplements"] = [h.id for h in extra]
            if state.get("overview") is not None:
                ranked = prefer_overview(ranked, state["overview"])
                state["prepared"].trace["context_ordering"] = "overview_title_section_preference"
            state["documents"] = [hit_to_document(h) for h in ranked]
        return state

    async def _web(self, state: dict) -> dict:
        """Compatibility entry for callers testing the combined policy; graph uses separate nodes."""
        await self._assess(state)
        return await self._search_web(state) if state["needs_web"] else state

    async def _assess(self, state: dict) -> dict:
        p = state["prepared"]
        mode = state.get("search_mode", "off")
        state["needs_web"] = False
        state["assessment_status"] = None
        if p.static_answer is not None or mode == "off":
            return state
        local = select_context(
            [document_to_hit(d) for d in state["documents"]],
            self.settings.rag_top_k,
            self.settings.rag_context_chars,
            policy=self.policy,
            spoilers=state["req"].options.spoilers,
            entities=state.get("entities"),
            query=state["req"].message + "\n" + state["query"],
        )
        context = [context_item(hit, i + 1) for i, hit in enumerate(local)]
        state["local"], state["local_context"] = local, context
        if state.get("diagnostic_queries"):
            p.trace["local_evidence_context"] = context
        status = None
        if mode == "auto":
            if context:
                spend(p.trace, "assessment", p.max_calls)
            status, diagnostic = await assess(
                self.llm,
                state["query"],
                [],  # Conversation memory resolves intent; it cannot make evidence sufficient.
                context,
                self.settings.web_search_assessment_seconds,
            )
            p.trace["evidence_assessment"] = diagnostic
            state["assessment_status"] = status
            p.trace["web_search"]["trigger"] = diagnostic["decision"]
            if status == "sufficient":
                p.trace["web_search"]["status"] = "local_sufficient"
                return state
            if status == "ambiguous":
                p.static_answer = (
                    "Bạn muốn hỏi cụ thể điều gì?" if p.lang == "vi" else "Could you clarify your question?"
                )
                return state
        state["needs_web"] = True
        return state

    async def _search_web(self, state: dict) -> dict:
        p = state["prepared"]
        local, context = state["local"], state["local_context"]
        status = state.get("assessment_status")
        try:
            if self.web_search is None:
                raise WebSearchError("not_configured")
            search_query = state["query"]
            if state.get("overview") is not None:
                search_query += "\nSearch focus: " + state["overview"].focus
            search_query, query_kind = web_query(search_query)
            p.trace["web_search"]["query_kind"] = query_kind
            if state.get("diagnostic_queries"):
                p.trace["web_search"]["query"] = search_query
            web, diagnostic = await self.web_search.search(search_query)
            p.trace["web_search"].update(status="ok", **diagnostic)
            state["web_hits"] = web
        except WebSearchError as exc:
            p.trace["web_search"].update(status="error", reason=exc.reason)
            if status is None and local:
                spend(p.trace, "assessment", p.max_calls)
                status, diagnostic = await assess(
                    self.llm,
                    state["query"],
                    [],
                    context,
                    self.settings.web_search_assessment_seconds,
                )
                p.trace["evidence_assessment"] = diagnostic
                p.trace["web_search"]["trigger"] = diagnostic["decision"]
            if status != "sufficient":
                raise UnavailableError("Tìm trên web đang gặp sự cố. Vui lòng thử lại sau.") from None
        return state

    def _context(self, state: dict) -> dict:
        p = state["prepared"]
        if p.static_answer is None:
            p.hits = select_context(
                merge_evidence([document_to_hit(d) for d in state["documents"]], state.get("web_hits", [])),
                self.settings.rag_top_k,
                self.settings.rag_context_chars,
                policy=self.policy,
                spoilers=state["req"].options.spoilers,
                entities=state.get("entities"),
                query=state["req"].message + "\n" + state["query"],
            )
            p.trace["selected_ids"] = [h.id for h in p.hits]
            if not p.hits:
                p.static_answer = (
                    no_overview_evidence(state["overview"], p.lang)
                    if state.get("overview") is not None
                    else (
                        "Mình chưa thể trả lời chắc chắn chi tiết này. "
                        "Bạn có thể nêu tên trang bị, boss, nhiệm vụ hoặc chi tiết cần kiểm tra không?"
                        if p.lang == "vi"
                        else "I can't confirm this detail yet. "
                        "Could you name the equipment, boss, quest or specific detail you want to check?"
                    )
                )
        return state

    def _prompt(self, state: dict) -> Prepared:
        p, req = state["prepared"], state["req"]
        p.template = self.template
        p.values = {
            "persona": prompt("persona"),
            "lang": p.lang,
            "spoilers": req.options.spoilers,
            "policy": prompt("answer" if p.mode == "rag" else "llm_only")
            + ("\n" + prompt("overview") if state.get("overview") is not None else ""),
            # In RAG, old turns cannot bias generation or masquerade as new evidence.
            # In llm_only, selected USER context remains explicitly conversational, never assistant claims.
            "history": [] if p.mode == "rag" else state["history"],
            "payload": json.dumps(
                {
                    "question": state.get("resolved_question", req.message),
                    "evidence": [context_item(h, i) for i, h in enumerate(p.hits, 1)],
                },
                ensure_ascii=False,
            ),
        }
        if state.get("next_player") is not None:
            player = state["next_player"]
            p.values["player_profile"] = (
                {c["key"]: c["value"] for c in player.get("constraints", [])}
                if isinstance(player, dict)
                else dict(player.slots)
            )
        p.messages = convert_to_openai_messages(self.template.invoke(p.values).to_messages())
        p.trace["prepare_ms"] = round((time.perf_counter() - state["started"]) * 1000, 2)
        return p
