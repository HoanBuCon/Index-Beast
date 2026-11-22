"""LangGraph request preparation; clients stay outside invocation state/checkpoints.

Một đường RAG duy nhất: vòng lặp Agent (gọi tool) → context → prompt; Generator viết câu trả lời.
Backend chỉ giữ guard xác định (schema, provenance, citation, budget, quyền bộ nhớ).

Phụ trách: TV3 · [S2–S3] Pipeline
"""

import inspect
import json
import time
from typing import TypedDict
from urllib.parse import urlsplit

from langchain_core.documents import Document
from langchain_core.messages import convert_to_openai_messages
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.adapters.tavily import WebHit, web_hit_allowed
from app.api.schemas.chat import ChatRequest
from app.rag.evidence import evidence_units
from app.rag.generator import LLM, Generator, Prepared
from app.rag.prompts import generation_prompt, prompt
from app.rag.retriever import document_to_hit
from core.config import Settings
from core.corpus import CorpusPolicy
from core.errors import AppError, UnavailableError
from core.types import Hit


class PreparationState(TypedDict, total=False):
    req: ChatRequest
    trace: dict
    history: list[dict]
    resolved_question: str
    answer_language: str
    started: float
    prepared: Prepared
    diagnostic_queries: bool
    player: object
    next_player: object
    documents: list[Document]
    web_hits: list[WebHit]
    overview: bool
    search_mode: str
    memory_scope: object
    memory_candidates: list[dict]
    recent_turns: list[dict]
    turn_profile: dict
    agent_results: str
    verify_coverage: bool


def content_key(hit: Hit) -> str | None:
    p = hit.payload
    # Không gộp nguồn gốc không rõ hoặc khác mục, khác điều kiện/bản phát hành/ảnh.
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
) -> list[Hit]:
    """Chỉ nhận vào, khử trùng và ngân sách. Thứ tự là của Agent (hoặc của retrieval), không bao giờ xếp lại ở đây."""
    admission = policy or CorpusPolicy()
    selected, seen, seen_content, used = [], set(), set(), 0
    for hit in hits:
        p = hit.payload
        if not isinstance(hit, WebHit) and admission.exclusion_reason(p):
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
            continue  # Chỉ lấy nguyên chunk: không lặng lẽ cắt hội thoại/điều kiện.
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
    # Giữ nguyên giá trị unknown/null được cung cấp, không bịa metadata còn thiếu hay tốn ngân sách cho nó.
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
            ("agent", self._agent),
            ("context", self._context),
            ("prompt", self._prompt_node),
        ):
            graph.add_node(name, self._guarded(name, node))
        graph.add_edge(START, "scope")
        graph.add_edge("scope", "memory")
        graph.add_edge("memory", "agent")
        graph.add_conditional_edges(
            "agent",
            lambda s: "answer" if s["prepared"].static_answer is not None else "context",
            {"context": "context", "answer": "prompt"},
        )
        graph.add_edge("context", "prompt")
        graph.add_edge("prompt", END)
        # State riêng cho mỗi lần gọi, ghi đè; không dùng MessagesState/append reducer hay checkpointer dùng chung.
        self.prepare_graph = graph.compile(name="indexbeast_prepare")

    @staticmethod
    def _guarded(name, node):
        async def run(state: PreparationState):
            started = time.perf_counter()
            if (trace := state.get("trace")) is not None:
                # Phần chẩn đoán hạn chót đọc giá trị này khi lượt bị hủy giữa node.
                trace["current_node"] = name
            try:
                result = node(state)
                if inspect.isawaitable(result):
                    result = await result
                trace = state["prepared"].trace
                trace.setdefault("graph_nodes", []).append(name)
                trace.setdefault("node_ms", {})[name] = round((time.perf_counter() - started) * 1000, 2)
                trace.pop("current_node", None)
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
        trace: dict | None = None,
    ) -> Prepared:
        """`trace` là dict của bên gọi cho trace của lượt, để thông tin chẩn đoán còn lại khi lượt bị hủy."""
        state = {
            "req": req,
            "history": history,
            "trace": trace if trace is not None else {},
            "started": started if started is not None else time.perf_counter(),
            "diagnostic_queries": diagnostic_queries,
            "player": player,
            "memory_scope": memory_scope,
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
        # Không đoán từ tin nhắn (22/11): lựa chọn của người chơi, nếu không thì ngôn ngữ Agent khai báo (mặc định vi).
        lang = req.options.lang if req.options.lang != "auto" else "vi"
        trace = state.get("trace")
        if trace is None:
            trace = state["trace"] = {}
        trace["mode"] = mode
        prepared = Prepared(mode, lang, [], trace=trace)
        state.update(prepared=prepared, documents=[], answer_language=lang)
        # Cùng mặc định trên mọi kênh (22/11: Discord không còn bị ép auto); Agent tự quyết khi nào tìm kiếm.
        requested = req.options.web_search or self.settings.web_search_mode
        state["search_mode"] = requested if self.settings.web_search_available else "off"
        prepared.trace["web_search"] = {"requested": requested, "mode": state["search_mode"], "status": "not_run"}
        state["verify_coverage"] = self.web_search is not None and state["search_mode"] == "auto"
        if not state["verify_coverage"]:
            prepared.max_calls = self.settings.chat_agent_max_calls
        return state

    async def _agent(self, state):
        from app.rag.true_agent import run_agent

        return await run_agent(self, state)

    def _bounded(self, rows: list[dict]) -> list[dict]:
        # Số ứng viên và số ký tự là ngân sách, không phải quyết định về độ liên quan ngữ nghĩa.
        bounded, used = [], 0
        for row in rows[: self.settings.chat_history_messages]:
            text = row.get("text", row.get("content", ""))
            if used + len(text) <= self.settings.chat_history_chars:
                bounded.append(row)
                used += len(text)
        return bounded

    def _recent_turns(self, history: list[dict]) -> list[dict]:
        """Các lượt gần nhất của hội thoại này (người chơi và trợ lý), trong ngân sách lịch sử.

        Giúp Agent trả lời câu hỏi về chính cuộc hội thoại ("tôi vừa hỏi gì?"). Không bao giờ là evidence
        về game: Agent chỉ nhắc lại chúng trong reply. Lượt cũ hơn bị bỏ trước.
        """
        rows, used = [], 0
        for msg in reversed(history[-self.settings.chat_history_messages :]):
            text = (msg.get("content") or "")[:800]
            if not text or used + len(text) > self.settings.chat_history_chars:
                break
            rows.append({"role": msg.get("role"), "text": text})
            used += len(text)
        return list(reversed(rows))

    async def _memory(self, state: PreparationState) -> dict:
        p, req = state["prepared"], state["req"]
        if not self.settings.chat_history_messages or not self.settings.chat_history_chars:
            state["memory_candidates"], state["history"], state["recent_turns"] = [], [], []
            p.trace["memory"] = {"method": "disabled", "status": "disabled"}
            return state
        if self.memory is not None and state.get("memory_scope") is not None:
            rows, diagnostic = await self.memory.recall(state["memory_scope"], req.message)
        else:
            # Chế độ RAM không tuyên bố có bộ nhớ bền/ngữ nghĩa. Chỉ đưa hai mốc là câu của người dùng.
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
        state["recent_turns"] = self._recent_turns(state["history"])
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
            # Chỉ evidence Agent đã chọn (22/11: server không còn dự phòng bằng mọi thứ tìm được).
            web_hits = [h for h in state.get("web_hits", []) if web_hit_allowed(h, self.settings)]
            by_id = {h.id: h for h in [document_to_hit(d) for d in state["documents"]] + web_hits}
            p.trace.setdefault("evidence_selection", {"method": "model", "ids": []})
            candidates = [by_id[i] for i in p.trace["evidence_selection"]["ids"] if i in by_id]
            p.hits = select_context(
                candidates,
                self.settings.rag_top_k,
                self.settings.rag_context_chars,
                policy=self.policy,
            )
            p.trace["selected_ids"] = [h.id for h in p.hits]
            # Không có evidence: bước viết nói rõ còn thiếu gì (câu trả lời insufficient), không phải một câu cố định
            # của server.
        return state

    def _prompt(self, state: dict) -> Prepared:
        p, req = state["prepared"], state["req"]
        player = state.get("next_player")
        # Điều kiện của lượt này, gồm cả các giả định Agent đã nêu (không lưu vào player).
        profile = state.get("turn_profile")
        if profile is None:
            profile = {c["key"]: c["value"] for c in player.get("constraints", [])} if isinstance(player, dict) else {}
        p.template = self.template
        p.values = {
            "persona": prompt("persona"),
            "lang": p.lang,
            "policy": prompt("answer")
            + ("\n" + prompt("gameplay_advice") if p.gameplay_advice else "")
            + ("\n" + prompt("overview") if state.get("overview") else ""),
            # Lượt cũ không thể làm lệch phần sinh câu trả lời hay giả làm evidence mới.
            "history": [],
            "payload": json.dumps(
                {
                    "question": state.get("resolved_question", req.message),
                    "original_user_message": req.message,
                    "answer_language": "Vietnamese (tiếng Việt)" if p.lang == "vi" else "English",
                    "evidence": [context_item(h, i) for i, h in enumerate(p.hits, 1)],
                    **({"player_profile": profile} if profile else {}),
                    # Các số Agent tính bằng run_python (ví dụ phân bổ build); dùng nguyên như vậy.
                    **({"agent_results": state["agent_results"]} if state.get("agent_results") else {}),
                },
                ensure_ascii=False,
            ),
        }
        if player is not None:
            p.values["player_profile"] = profile
        p.messages = convert_to_openai_messages(self.template.invoke(p.values).to_messages())
        p.trace["prepare_ms"] = round((time.perf_counter() - state["started"]) * 1000, 2)
        return p
