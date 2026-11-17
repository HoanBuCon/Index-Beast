"""LangGraph request preparation; clients stay outside invocation state/checkpoints.

Một đường RAG duy nhất: Agent quyết định → Tool Agent thu thập bằng chứng → context → prompt.
Backend chỉ giữ guard xác định (schema, provenance, citation, budget, quyền bộ nhớ).

Phụ trách: TV3 · [S2–S3] Pipeline
"""

import inspect
import json
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

from app.adapters.tavily import WebHit
from app.api.schemas.chat import ChatRequest, Clarification
from app.rag.agent import condition_changes, decide, inactive_conditions
from app.rag.evidence import evidence_units
from app.rag.generator import LLM, Generator, Prepared
from app.rag.prompts import generation_prompt, prompt
from app.rag.retriever import document_to_hit
from app.rag.task_plan import start_plan
from app.rag.web_search import merge_evidence
from core.config import Settings
from core.corpus import CorpusPolicy
from core.errors import AppError, BadRequestError, UnavailableError, UpstreamError
from core.types import Hit


class PreparationState(TypedDict, total=False):
    req: ChatRequest
    history: list[dict]
    original_question: str
    resolved_question: str
    query: str  # Retrieval query; never used to change the answer language.
    answer_language: str
    started: float
    prepared: Prepared
    diagnostic_queries: bool
    gameplay: bool
    player: object
    next_player: object
    documents: list[Document]
    web_hits: list[WebHit]
    overview: bool
    search_mode: str
    memory_scope: object
    memory_candidates: list[dict]
    name_to_check: str
    verify_coverage: bool


def language(question: str, requested: str) -> str:
    """Provisional language before the Agent decides; RAG overrides it with answer_language."""
    if requested != "auto":
        return requested
    normalized = unicodedata.normalize("NFD", question.lower())
    return "vi" if any(unicodedata.combining(c) for c in normalized) or "đ" in question.lower() else "en"


def content_key(hit: Hit) -> str | None:
    p = hit.payload
    # Do not collapse unknown provenance or different sections, conditions/releases/images.
    if not p.get("source_id") or not p.get("revision_id"):
        return None
    keys = (
        "source",
        "source_id",
        "revision_id",
        "url",
        "section",
        "text",
        "lang",
        "game_scope",
        "release_scope",
        "speaker",
        "trigger",
        "variant_context",
        "image_ids",
        "image_association",
        "source_type",
        "source_type_evidence",
        "unit_kind",
        "review_status",
        "spoiler_level",
        "indexbeast_admission",
        "game_version",
        "patch_version",
        "upgrade_level",
        "affinity",
        "ng_cycle",
    )
    return json.dumps({key: p.get(key) for key in keys}, sort_keys=True, ensure_ascii=False)


def select_context(
    hits: list[Hit],
    limit: int,
    budget: int,
    *,
    policy: CorpusPolicy | None = None,
    spoilers: bool = True,
) -> list[Hit]:
    """Admission, dedup and budget only. Order is the Agent's (or retrieval's) order, never re-ranked here."""
    admission = policy or CorpusPolicy()
    selected, seen, seen_content, used = [], set(), set(), 0
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
    if isinstance(hit, WebHit):
        item["source_domain"] = urlsplit(p["url"]).hostname
    units = evidence_units(p["text"])
    item["evidence_units"] = {"q0": "entire source text above"} if "q0" in units else units
    return item


class ChatPipeline:
    def __init__(
        self,
        settings: Settings,
        llm: LLM | None,
        retriever: BaseRetriever | None = None,
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
        self.generator = (
            Generator(llm, thinking=settings.rag_thinking_enabled, format_retries=settings.rag_format_retries)
            if llm is not None
            else None
        )
        self.template = generation_prompt()
        graph = StateGraph(PreparationState)
        for name, node in (
            ("scope", self._scope),
            ("memory", self._memory),
            ("agent_decision", self._agent),
            ("tool_agent", self._tool_agent),
            ("context", self._context),
            ("prompt", self._prompt_node),
        ):
            graph.add_node(name, self._guarded(name, node))
        graph.add_edge(START, "scope")
        graph.add_edge("scope", "memory")
        graph.add_conditional_edges(
            "memory", lambda s: "agent" if self._rag(s) else "answer", {"agent": "agent_decision", "answer": "prompt"}
        )
        graph.add_conditional_edges(
            "agent_decision",
            lambda s: "answer" if s["prepared"].static_answer is not None else "tools",
            {"tools": "tool_agent", "answer": "prompt"},
        )
        graph.add_edge("tool_agent", "context")
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
        player=None,
        memory_scope=None,
        started: float | None = None,
    ) -> Prepared:
        state = {
            "req": req,
            "history": history,
            "started": started if started is not None else time.perf_counter(),
            "diagnostic_queries": diagnostic_queries,
            "player": player,
            "memory_scope": memory_scope,
            "original_question": req.message,
            "resolved_question": req.message,
        }
        with tracing_context(enabled=False):
            result = await self.prepare_graph.ainvoke(state, config={"recursion_limit": 24})
            return result["prepared"]

    @staticmethod
    def _rag(state: PreparationState) -> bool:
        return state["prepared"].mode == "rag"

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
        if self._rag(state):
            state["verify_coverage"] = (
                self.web_search is not None and state["search_mode"] == "auto" and req.options.spoilers
            )
            if not state["verify_coverage"]:
                prepared.max_calls = self.settings.chat_agent_max_calls
        return state

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
            self.settings.model_copy(update={"chat_agent_max_calls": None})
            if state.get("verify_coverage")
            else self.settings,
            p.trace,
            shared_thread=shared_thread,
            requested_lang=req.options.lang,
        )
        if decision is None:
            raise UpstreamError("Mô hình chưa trả quyết định hợp lệ. Vui lòng thử lại.")
        p.agent_decision = decision.model_dump()
        p.gameplay_advice = (
            decision.action == "retrieve"
            and decision.intent in {"mechanics", "build", "gameplay_comparison"}
            and req.options.spoilers
        )
        if req.options.lang == "auto" and decision.answer_language:
            p.lang = state["answer_language"] = decision.answer_language
        continuing = decision.turn_type != "new" and decision.intent != "cancel"
        changes = condition_changes(decision, working)
        inactive = inactive_conditions(decision, working, changes)
        rounds = working.get("clarification_rounds", 0) if continuing and pending else 0
        limit = self.settings.chat_clarification_max_rounds
        if decision.action == "clarify" and limit is not None and rounds >= limit:
            raise UnavailableError(
                "Đã đạt giới hạn hỏi bổ sung. Bạn có thể gửi yêu cầu cụ thể hơn hoặc hủy yêu cầu này."
            )
        p.player_state = {
            "constraints": [c.model_dump() for c in decision.constraints],
            "original": working.get("original", req.message) if continuing else req.message,
            "request_text": working.get("request_text", req.message) if continuing else req.message,
            "clarification_rounds": rounds + int(decision.action == "clarify"),
            "intent": decision.intent,
            "lang": p.lang,
            "pending": None,
            "updated": time.time(),
        }
        if inactive:
            p.player_state["inactive_conditions"] = inactive
        if changes:
            p.trace["updated_condition_keys"] = sorted({c.key for c in changes})
            active_keys = {c.key for c in decision.constraints}
            p.player_state["retired_condition_keys"] = sorted({c.key for c in changes} - active_keys)
        if decision.turn_type == "clarification_reply" and pending and working.get("plan") and not changes:
            p.player_state["plan"] = [{**item} for item in working["plan"]]
            p.player_state["plan_evidence"] = working.get("plan_evidence", [])
        elif decision.subgoals:
            p.player_state["plan"] = start_plan(decision.subgoals)
        state["next_player"] = p.player_state
        if decision.intent == "cancel":
            p.player_state = state["next_player"] = {"updated": time.time(), "constraints": [], "pending": None}
        state["history"] = []
        state["name_to_check"] = decision.name_to_check
        state["query"] = decision.search_query if decision.rewrite else req.message
        state["resolved_question"] = decision.resolved_question or req.message
        state["gameplay"] = decision.intent in {"build", "route", "quest", "mechanics", "acquisition"}
        # Overview is the Agent's intent decision, not a keyword table.
        state["overview"] = decision.action == "retrieve" and decision.intent == "overview"
        if state["overview"]:
            p.trace["request_kind"] = "overview"
        fallback = p.trace["agent"]["reason"] == "original_query_fallback"
        p.trace["rewrite_fallback"] = fallback
        p.trace["rewrite"] = {
            "status": "fallback" if fallback else "accepted" if decision.rewrite else "not_run",
            "reason": "original_query_fallback" if fallback else "agent_decision",
            "model_calls": 0,
        }
        p.trace["rewritten_query"] = state["query"]
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
            if p.player_state.get("plan"):
                p.trace["task_plan"] = p.player_state["plan"]
        if decision.action != "retrieve":
            p.static_answer = decision.reply
        return state

    async def _tool_agent(self, state):
        from app.rag.tool_agent import run_tools

        return await run_tools(self, state)

    def _bounded(self, rows: list[dict]) -> list[dict]:
        # Candidate count and chars are budgets, not semantic relevance decisions.
        bounded, used = [], 0
        for row in rows[: self.settings.chat_history_messages]:
            text = row.get("text", row.get("content", ""))
            if used + len(text) <= self.settings.chat_history_chars:
                bounded.append(row)
                used += len(text)
        return bounded

    async def _memory(self, state: PreparationState) -> dict:
        p, req = state["prepared"], state["req"]
        if not self.settings.chat_history_messages or not self.settings.chat_history_chars:
            state["memory_candidates"], state["history"] = [], []
            p.trace["memory"] = {"method": "disabled", "status": "disabled"}
            return state
        if not self._rag(state):
            # llm_only: recent USER turns only, newest last; the model decides whether they relate.
            users = [r for r in state["history"] if r.get("role") == "user"][::-1]
            rows = self._bounded(users)[::-1]
            state["history"] = [{"role": "user", "content": r["content"]} for r in rows]
            p.trace["memory"] = {"method": "recent_user_turns", "selected": len(rows)}
            return state
        if self.memory is not None and state.get("memory_scope") is not None:
            rows, diagnostic = await self.memory.recall(state["memory_scope"], req.message)
        else:
            # RAM mode has no claim of durable/semantic memory. Supply only two user anchors.
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
        rows = self._bounded(rows)
        if req.channel == "discord" and (req.external_ref or "").startswith("discord:thread:"):
            rows = [row for row in rows if row.get("kind") != "fact"]
        state["memory_candidates"] = rows
        state["history"] = []
        p.trace["memory"] = diagnostic
        return state

    def _prompt_node(self, state: PreparationState) -> dict:
        return {"prepared": self._prompt(state)}

    def _context(self, state: dict) -> dict:
        p = state["prepared"]
        if p.static_answer is None:
            original_candidates = [document_to_hit(d) for d in state["documents"]] + state.get("web_hits", [])
            selection = p.trace.get("evidence_selection", {})
            ids = selection.get("ids", [])
            if p.checked_build is not None:
                ids = list(dict.fromkeys([*p.checked_build["sources"], *ids]))[:5]
            if ids or selection.get("method") == "model":
                by_id = {h.id: h for h in original_candidates}
                candidates = [by_id[i] for i in ids if i in by_id]
            else:
                candidates = merge_evidence([document_to_hit(d) for d in state["documents"]], state.get("web_hits", []))
                p.trace.setdefault("evidence_selection", {"method": "rank_fallback", "ids": []})
            p.hits = select_context(
                candidates,
                self.settings.rag_top_k,
                self.settings.rag_context_chars,
                policy=self.policy,
                spoilers=state["req"].options.spoilers,
            )
            p.trace["selected_ids"] = [h.id for h in p.hits]
            checks = p.trace.get("coverage_checks", [])
            if checks:
                check = checks[-1]
                if check["status"] in {"sufficient", "partial"} and check.get("context_ids") == p.trace["selected_ids"]:
                    p.trace["answer_coverage"] = {key: check[key] for key in ("status", "covered", "missing")}
            if not p.hits and not p.gameplay_advice:
                p.static_answer = (
                    "Mình chưa có đủ thông tin để trả lời câu này."
                    if p.lang == "vi"
                    else "I don't have enough information to answer this question."
                )
        return state

    def _prompt(self, state: dict) -> Prepared:
        p, req = state["prepared"], state["req"]
        player = state.get("next_player")
        profile = {c["key"]: c["value"] for c in player.get("constraints", [])} if isinstance(player, dict) else {}
        p.template = self.template
        p.values = {
            "persona": prompt("persona"),
            "lang": p.lang,
            "spoilers": req.options.spoilers,
            "policy": prompt("answer" if p.mode == "rag" else "llm_only")
            + ("\n" + prompt("gameplay_advice") if p.gameplay_advice else "")
            + ("\n" + prompt("overview") if state.get("overview") else ""),
            # In RAG, old turns cannot bias generation or masquerade as new evidence.
            # In llm_only, recent USER context remains explicitly conversational, never assistant claims.
            "history": [] if p.mode == "rag" else state["history"],
            "payload": json.dumps(
                {
                    "question": state.get("resolved_question", req.message),
                    "original_user_message": req.message,
                    "answer_language": "Vietnamese (tiếng Việt)" if p.lang == "vi" else "English",
                    "evidence": [context_item(h, i) for i, h in enumerate(p.hits, 1)],
                    "checked_build": p.checked_build,
                    **({"evidence_coverage": p.trace["answer_coverage"]} if "answer_coverage" in p.trace else {}),
                    **({"player_profile": profile} if profile else {}),
                    **({"task_plan": p.trace["task_plan"]} if p.trace.get("task_plan") else {}),
                    **({"verified_name": p.trace["verified_name"]} if p.trace.get("verified_name") else {}),
                },
                ensure_ascii=False,
            ),
        }
        if player is not None:
            p.values["player_profile"] = profile
        p.messages = convert_to_openai_messages(self.template.invoke(p.values).to_messages())
        p.trace["prepare_ms"] = round((time.perf_counter() - state["started"]) * 1000, 2)
        return p
