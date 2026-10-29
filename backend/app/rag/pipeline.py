"""One orchestration path; explicit llm_only/rag, no hidden fallback or automatic web search.

Phụ trách: TV3 · [S2–S3] Pipeline
"""

import json
import re
import time
import unicodedata
from urllib.parse import urlsplit

from langchain_core.messages import convert_to_openai_messages
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from langsmith import tracing_context

from app.rag.evidence import evidence_units
from app.rag.generator import LLM, Generator, Prepared
from app.rag.prompts import generation_prompt, prompt
from app.rag.reranker import NoReranker, Reranker
from app.rag.retriever import document_to_hit, hit_to_document
from app.rag.rewrite import rewrite
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
        or re.search(r"\b(la ai|tai sao|cho toi|nhan vat|cot truyen|o dau)\b", question.lower())
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


def unresolved_reference(question: str) -> bool:
    """Conservative pronoun-leading gate, not NER. A named/content prefix is left to the LLM/rewrite."""
    pronoun = re.search(r"\b(ông ta|cô ấy|anh ấy|he|she|him|her)\b", question, re.I)
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
    selected, seen, used = [], set(), 0
    for hit in hits:
        p = hit.payload
        if hit.id in seen or admission.exclusion_reason(p, spoilers=spoilers):
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
    ):
        self.settings, self.llm, self.retriever = settings, llm, retriever
        self.policy = CorpusPolicy.from_settings(settings)
        store = getattr(retriever, "store", None)
        if store is not None and store.policy != self.policy:
            raise ValueError("Retriever and pipeline must use the same corpus policy/languages")
        self.reranker = (reranker or NoReranker()) if settings.chat_mode == "rag" else None
        self.generator = Generator(llm, thinking=settings.rag_thinking_enabled) if llm is not None else None
        self.template = generation_prompt()
        rag_steps = (
            RunnableLambda(self._rewrite, name="rewrite")
            | RunnableLambda(self._retrieve, name="hybrid_retrieve")
            | RunnableLambda(self._rerank, name="optional_rerank")
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

    async def prepare(self, req, history: list[dict]) -> Prepared:
        with tracing_context(enabled=False):
            return await self.prepare_chain.ainvoke({"req": req, "history": history, "started": time.perf_counter()})

    def _scope(self, state: dict) -> dict:
        req = state["req"]
        if self.llm is None:
            raise UnavailableError("Chưa cấu hình DeepSeek API key.")
        mode = self.settings.chat_mode
        lang = language(req.message, req.options.lang)
        prepared = Prepared(mode, lang, [], trace={"mode": mode, "rewrite_fallback": False})
        state.update(prepared=prepared, query=req.message, documents=[])
        if outside_scope(req.message):
            prepared.static_answer = (
                "Mình có thể giúp bạn về Elden Ring: cốt truyện, nhiệm vụ, trang bị, cơ chế và hướng build. "
                "Bạn muốn tìm hiểu phần nào trong game?"
                if lang == "vi"
                else "I can help with Elden Ring lore, quests, equipment, mechanics and build ideas. "
                "What would you like to explore in the game?"
            )
        return state

    async def _rewrite(self, state: dict) -> dict:
        p = state["prepared"]
        if self.settings.rag_rewrite_enabled:
            rewritten, fallback = await rewrite(self.llm, state["query"], state["history"], p.lang)
            p.trace["rewrite_fallback"] = fallback
            if rewritten.out_of_scope:
                p.static_answer = (
                    "Mình hỗ trợ các câu hỏi về Elden Ring, từ cốt truyện đến gameplay và build."
                    if p.lang == "vi"
                    else "I help with Elden Ring questions, from lore to gameplay and builds."
                )
            elif rewritten.ambiguous:
                p.static_answer = (
                    "Bạn đang hỏi nhân vật, trang bị, boss hoặc nhiệm vụ nào trong Elden Ring?"
                    if p.lang == "vi"
                    else "Which Elden Ring character, equipment, boss or quest do you mean?"
                )
            else:
                state["query"] = rewritten.standalone_query_en
        elif not state["history"] and unresolved_reference(state["query"]):
            p.static_answer = "Bạn đang hỏi nhân vật nào?" if p.lang == "vi" else "Which character do you mean?"
        return state

    async def _retrieve(self, state: dict) -> dict:
        if state["prepared"].static_answer is None:
            if self.retriever is None:
                raise UnavailableError("Kho tri thức RAG chưa được cấu hình.")
            # Copy only the Pydantic retriever wrapper; clients/encoder remain shared.
            retriever = self.retriever.model_copy(update={"spoilers": state["req"].options.spoilers})
            state["documents"] = await retriever.ainvoke(state["query"])
            state["prepared"].trace["retrieved"] = [
                {"id": h.id, "score": h.score} for h in map(document_to_hit, state["documents"])
            ]
        return state

    async def _rerank(self, state: dict) -> dict:
        if state["prepared"].static_answer is None:
            hits = [document_to_hit(d) for d in state["documents"]]
            ranked = await self.reranker.rank(state["query"], hits)
            state["documents"] = [hit_to_document(h) for h in ranked]
        return state

    def _context(self, state: dict) -> dict:
        p = state["prepared"]
        if p.static_answer is None:
            p.hits = select_context(
                [document_to_hit(d) for d in state["documents"]],
                self.settings.rag_top_k,
                self.settings.rag_context_chars,
                policy=self.policy,
                spoilers=state["req"].options.spoilers,
            )
            p.trace["selected_ids"] = [h.id for h in p.hits]
            if not p.hits:
                p.static_answer = (
                    "Mình chưa tìm được nguồn đủ sát câu hỏi này để trả lời chắc chắn. "
                    "Bạn có thể nêu tên trang bị, boss, nhiệm vụ hoặc chi tiết cần kiểm tra không?"
                    if p.lang == "vi"
                    else "I couldn't find evidence close enough to answer reliably. "
                    "Could you name the equipment, boss, quest or specific detail you want to check?"
                )
        return state

    def _prompt(self, state: dict) -> Prepared:
        p, req = state["prepared"], state["req"]
        p.template = self.template
        p.values = {
            "persona": prompt("persona"),
            "lang": p.lang,
            "spoilers": req.options.spoilers,
            "policy": prompt("answer" if p.mode == "rag" else "llm_only"),
            "history": state["history"],
            "payload": json.dumps(
                {"question": req.message, "evidence": [context_item(h, i) for i, h in enumerate(p.hits, 1)]},
                ensure_ascii=False,
            ),
        }
        p.messages = convert_to_openai_messages(self.template.invoke(p.values).to_messages())
        p.trace["prepare_ms"] = round((time.perf_counter() - state["started"]) * 1000, 2)
        return p
