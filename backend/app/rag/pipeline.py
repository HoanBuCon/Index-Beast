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

from app.rag.generator import LLM, Generator, Prepared
from app.rag.prompts import generation_prompt, prompt
from app.rag.reranker import NoReranker, Reranker
from app.rag.retriever import document_to_hit, hit_to_document
from app.rag.rewrite import rewrite
from core.config import Settings
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
            r"\b(nightreign|shadow of the erdtree|dlc|dark souls|bitcoin|fibonacci|cover letter|"
            r"gaming laptop|python code|viet.*chuong trinh|build pvp|pvp build|toi uu.*chi so)\b",
            plain,
        )
    )


def select_context(hits: list[Hit], limit: int, budget: int) -> list[Hit]:
    selected, seen, used = [], set(), 0
    for hit in hits:
        p = hit.payload
        if hit.id in seen or p.get("game_scope") != "base" or p.get("review_status") != "approved":
            continue
        if p.get("source_type") not in {"in_game_text", "wiki_prose", "speculation"}:
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
    return {
        "index": index,
        "chunk_id": hit.id,
        "title": p["title"],
        "section": p.get("section"),
        "source_type": p["source_type"],
        "text": p["text"],
    }


class ChatPipeline:
    def __init__(
        self,
        settings: Settings,
        llm: LLM | None,
        retriever: BaseRetriever | None = None,
        reranker: Reranker | None = None,
    ):
        self.settings, self.llm, self.retriever = settings, llm, retriever
        self.reranker = (reranker or NoReranker()) if settings.chat_mode == "rag" else None
        self.generator = Generator(llm) if llm is not None else None
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
                "Mình chỉ hỗ trợ lore Elden Ring base game. Bạn hãy hỏi về câu chuyện trong game."
                if lang == "vi"
                else "I focus on Elden Ring base-game lore. Please ask about its story."
            )
        return state

    async def _rewrite(self, state: dict) -> dict:
        p = state["prepared"]
        if self.settings.rag_rewrite_enabled:
            rewritten, fallback = await rewrite(self.llm, state["query"], state["history"], p.lang)
            p.trace["rewrite_fallback"] = fallback
            if rewritten.out_of_scope or rewritten.ambiguous:
                p.static_answer = (
                    "Bạn hãy nêu rõ nhân vật/sự kiện thuộc lore base game muốn hỏi."
                    if p.lang == "vi"
                    else "Please specify the base-game character or event you mean."
                )
            else:
                state["query"] = rewritten.standalone_query_en
        elif not state["history"] and re.search(r"\b(ông ta|cô ấy|anh ấy|he|she|him|her)\b", state["query"], re.I):
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
            )
            p.trace["selected_ids"] = [h.id for h in p.hits]
            if not p.hits:
                p.static_answer = (
                    "Mình chưa có đủ bằng chứng trong kho tri thức để trả lời câu hỏi này."
                    if p.lang == "vi"
                    else "The knowledge base has insufficient evidence to answer this question."
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
