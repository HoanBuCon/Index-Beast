"""One orchestration path; explicit llm_only/rag, no hidden fallback or automatic web search.

Phụ trách: TV3 · [S2–S3] Pipeline
"""

import asyncio
import json
import re
import time
import unicodedata
from urllib.parse import urlsplit

from langchain_core.messages import convert_to_openai_messages
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from langsmith import tracing_context

from app.adapters.tavily import WebHit, WebSearchError
from app.rag.evidence import evidence_units
from app.rag.generator import LLM, Generator, Prepared
from app.rag.overview import detect_overview, no_overview_evidence, overview_queries, prefer_overview
from app.rag.prompts import generation_prompt, prompt
from app.rag.query_plan import content_key, fuse_ranked, plan_queries
from app.rag.reranker import NoReranker, Reranker
from app.rag.retriever import document_to_hit, hit_to_document
from app.rag.rewrite import contextual_followup, rewrite
from app.rag.web_search import assess, merge_evidence
from core.config import Settings
from core.corpus import CorpusPolicy
from core.errors import UnavailableError
from core.types import Hit


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
    hits: list[Hit], limit: int, budget: int, *, policy: CorpusPolicy | None = None, spoilers: bool = True
) -> list[Hit]:
    admission = policy or CorpusPolicy()
    selected, seen, seen_content, used = [], set(), set(), 0
    for hit in hits:
        p = hit.payload
        key = content_key(hit)
        if (
            hit.id in seen
            or (key is not None and key in seen_content)
            or (not isinstance(hit, WebHit) and admission.exclusion_reason(p, spoilers=spoilers))
            or (isinstance(hit, WebHit) and not spoilers)
        ):
            continue
        if not all(isinstance(p.get(k), str) and p[k].strip() for k in ("text", "title", "url")):
            continue
        if urlsplit(p["url"]).scheme not in {"https", "http"} or not urlsplit(p["url"]).netloc:
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
    ):
        self.settings, self.llm, self.retriever = settings, llm, retriever
        self.web_search = web_search
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
        rag_steps = (
            RunnableLambda(self._rewrite, name="rewrite")
            | RunnableLambda(self._retrieve, name="hybrid_retrieve")
            | RunnableLambda(self._rerank, name="optional_rerank")
            | RunnableLambda(self._web, name="optional_web_search")
            | RunnableLambda(self._context, name="select_numbered_context")
        )
        self.prepare_chain = (
            RunnableLambda(self._scope, name="scope_and_language")
            | RunnableBranch(
                (lambda state: state["prepared"].mode == "rag" and state["prepared"].static_answer is None, rag_steps),
                RunnablePassthrough(),
            )
            | RunnableLambda(self._prompt, name="prepare_chat_prompt")
        )

    async def prepare(self, req, history: list[dict], *, diagnostic_queries: bool = False) -> Prepared:
        state = {
            "req": req,
            "history": history,
            "started": time.perf_counter(),
            "diagnostic_queries": diagnostic_queries,
        }
        with tracing_context(enabled=False):
            try:
                return await self.prepare_chain.ainvoke(state)
            except UnavailableError as exc:
                if diagnostic_queries and "prepared" in state:
                    # Opt-in local benchmark data only; API error schema/loggers remain unchanged.
                    exc.rag_diagnostics = dict(state["prepared"].trace)
                raise

    def _scope(self, state: dict) -> dict:
        req = state["req"]
        if self.llm is None:
            raise UnavailableError("Chưa cấu hình DeepSeek API key.")
        mode = self.settings.chat_mode
        lang = language(req.message, req.options.lang)
        prepared = Prepared(mode, lang, [], trace={"mode": mode, "rewrite_fallback": False})
        state.update(prepared=prepared, query=req.message, documents=[])
        requested = "auto" if req.channel == "discord" else (req.options.web_search or self.settings.web_search_mode)
        state["search_mode"] = requested if self.settings.web_search_available else "off"
        prepared.trace["web_search"] = {"requested": requested, "mode": state["search_mode"], "status": "not_run"}
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
        if (
            mode == "rag"
            and prepared.static_answer is None
            and requested == "always"
            and not self.settings.web_search_available
        ):
            raise UnavailableError("Tìm trên web hiện chưa khả dụng. Chọn chế độ tự động hoặc thử lại sau.")
        if mode == "rag" and prepared.static_answer is None and self.settings.rag_overview_enabled:
            state["overview"] = detect_overview(req.message)
            if state["overview"] is not None:
                prepared.trace["request_kind"] = "overview"
                prepared.trace["overview_topic"] = state["overview"].topic
        return state

    async def _rewrite(self, state: dict) -> dict:
        p = state["prepared"]
        if state.get("overview") is not None:
            # A recognized global topic is already a valid scope, not an ambiguous referent.
            # The bounded overview query plan supplies English search cues without a paid rewrite call.
            p.trace["rewrite"] = {"status": "not_run", "reason": "overview_query_plan", "model_calls": 0}
            return state
        if self.settings.rag_rewrite_enabled or state.get("search_mode", "off") != "off":
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
            elif rewritten.ambiguous or (
                fallback
                and (
                    contextual_followup(state["query"])
                    or (not state["history"] and unresolved_reference(state["query"]))
                )
            ):
                p.static_answer = (
                    "Bạn đang hỏi nhân vật, trang bị, boss hoặc nhiệm vụ nào trong Elden Ring?"
                    if p.lang == "vi"
                    else "Which Elden Ring character, equipment, boss or quest do you mean?"
                )
            else:
                state["query"] = rewritten.standalone_query_en
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
            queries = plan_queries(state["req"].message, state["query"], self.settings.rag_query_mode)
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
            if state.get("overview") is not None:
                ranked = prefer_overview(ranked, state["overview"])
                state["prepared"].trace["context_ordering"] = "overview_title_section_preference"
            state["documents"] = [hit_to_document(h) for h in ranked]
        return state

    async def _web(self, state: dict) -> dict:
        p = state["prepared"]
        mode = state.get("search_mode", "off")
        if p.static_answer is not None or mode == "off":
            return state
        local = select_context(
            [document_to_hit(d) for d in state["documents"]],
            self.settings.rag_top_k,
            self.settings.rag_context_chars,
            policy=self.policy,
            spoilers=state["req"].options.spoilers,
        )
        context = [context_item(hit, i + 1) for i, hit in enumerate(local)]
        status = None
        if mode == "auto":
            status, diagnostic = await assess(
                self.llm,
                state["query"],
                state["history"],
                context,
                self.settings.web_search_assessment_seconds,
            )
            p.trace["evidence_assessment"] = diagnostic
            if status == "sufficient":
                p.trace["web_search"]["status"] = "local_sufficient"
                return state
            if status == "ambiguous":
                p.static_answer = (
                    "Bạn muốn hỏi cụ thể điều gì?" if p.lang == "vi" else "Could you clarify your question?"
                )
                return state
        try:
            if self.web_search is None:
                raise WebSearchError("not_configured")
            search_query = state["query"]
            if state.get("overview") is not None:
                search_query += "\nSearch focus: " + state["overview"].focus
            web, diagnostic = await self.web_search.search(search_query)
            p.trace["web_search"].update(status="ok", **diagnostic)
            state["web_hits"] = web
        except WebSearchError as exc:
            p.trace["web_search"].update(status="error", reason=exc.reason)
            if status is None and local:
                status, diagnostic = await assess(
                    self.llm,
                    state["query"],
                    state["history"],
                    context,
                    self.settings.web_search_assessment_seconds,
                )
                p.trace["evidence_assessment"] = diagnostic
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
            "history": state["history"],
            "payload": json.dumps(
                {"question": req.message, "evidence": [context_item(h, i) for i, h in enumerate(p.hits, 1)]},
                ensure_ascii=False,
            ),
        }
        p.messages = convert_to_openai_messages(self.template.invoke(p.values).to_messages())
        p.trace["prepare_ms"] = round((time.perf_counter() - state["started"]) * 1000, 2)
        return p
