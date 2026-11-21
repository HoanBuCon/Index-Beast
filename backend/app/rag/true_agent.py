"""True Agent: one native tool-calling loop prepares every RAG turn (GĐ2, 22/11/2026).

Replaces the former multi-role preparation (Agent decision → Tool planner → Assessor). The model decides what the
player asks, which conditions apply, what to search, whether a name is the one meant, whether to ask back and
which evidence supports the answer. The server only runs tools, checks them with deterministic guards (corpus
policy, provenance of player conditions, quoted numbers, arithmetic, web policy) and keeps the budget. Every
rejection goes back to the model as a tool result so it can fix its own call. The existing Generator and Answer
Guard still write and check the final answer from the evidence the Agent chose.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm import LLMError
from app.adapters.tavily import WebHit, WebSearchError
from app.api.schemas.chat import Clarification, ClarificationField
from app.rag.entity_spelling import matching_names
from app.rag.gameplay_knowledge import level_rule
from app.rag.matching import contains_name, contains_text
from app.rag.prompts import prompt
from app.rag.python_sandbox import run_python
from app.rag.retriever import document_to_hit, hit_to_document
from core.errors import UnavailableError, UpstreamError

logger = logging.getLogger(__name__)
STATE_TTL_SECONDS = 1800
ASSUMPTION = "assumption"
PREVIEW_CHARS = 320
RESULTS_PER_SEARCH = 8
INTENTS = Literal["lore", "acquisition", "mechanics", "build", "route", "quest", "comparison", "overview", "other"]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(_Args):
    query: str = Field(min_length=1, max_length=300, description="Focused English search query")


class NameArgs(_Args):
    name: str = Field(min_length=1, max_length=100, description="The player's spelling of the name")


class OpenArgs(_Args):
    ids: list[str] = Field(min_length=1, max_length=5, description="Evidence IDs from earlier tool results")


class Condition(_Args):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$", description="e.g. level, starting_class, weapon, goal")
    value: str = Field(min_length=1, max_length=120, description="Exactly as the player wrote it, or your assumption")
    source_id: str = Field(
        min_length=1,
        max_length=100,
        description='"current" or the memory/condition ID it came from; "assumption" for your own stated assumption',
    )


class ConditionArgs(_Args):
    set: list[Condition] = Field(default_factory=list, max_length=10, description="Conditions to add or replace")
    retire: list[str] = Field(default_factory=list, max_length=10, description="Keys the player withdrew or replaced")


class PythonArgs(_Args):
    code: str = Field(
        min_length=1,
        max_length=4000,
        description="A short Python calculation; print() what you need. No imports, files, network or names "
        "starting with an underscore.",
    )


class Missing(_Args):
    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=80, description="Short label in the player's language")


class AskArgs(_Args):
    question: str = Field(min_length=1, max_length=500, description="One natural question in the player's language")
    missing: list[Missing] = Field(min_length=1, max_length=2, description="What the player should tell you")
    answer_language: Literal["vi", "en"]


class ReplyArgs(_Args):
    text: str = Field(
        min_length=1, max_length=2000, description="Reply in the player's language, without new game facts"
    )
    answer_language: Literal["vi", "en"]
    about_conversation: bool = Field(
        default=False, description="The player asked about this conversation (what was asked or answered)"
    )
    end_task: bool = Field(default=False, description="The player cancelled the current request")
    unrelated: bool = Field(default=False, description="The request is not about Elden Ring")


class FinishArgs(_Args):
    request: str = Field(min_length=1, max_length=1000, description="The player's request as one standalone question")
    intent: INTENTS
    answer_language: Literal["vi", "en"]
    evidence_ids: list[str] = Field(
        default_factory=list, max_length=5, description="Up to 5 evidence IDs that best support the answer"
    )
    gameplay_advice: bool = Field(default=False, description="General gameplay know-how may supplement evidence")
    needs_reasoning: bool = Field(
        default=False,
        description="The writer must weigh things before answering: sources disagree or depend on conditions "
        "(patch, NG+, one- vs two-handed), several options compared on several criteria, or a quest/route whose "
        "steps must be ordered. False for a single fact, single-source lore, or a build already computed in results",
    )
    results: str = Field(
        default="",
        max_length=3000,
        description="Results you computed with run_python that the answer must use as they are (e.g. the final "
        "eight-attribute allocation, its total, and which values are assumptions)",
    )


TOOLS = {
    "search_corpus": (SearchArgs, "Search the local Elden Ring wiki corpus."),
    "search_web": (SearchArgs, "Search the web when the corpus cannot fill a gap."),
    "check_name": (NameArgs, "Look up a possibly misspelled proper name; returns candidate titles."),
    "open_evidence": (OpenArgs, "Show the full text and quote IDs of evidence already seen."),
    "set_conditions": (ConditionArgs, "Record or retire the player's conditions (level, class, weapon, goal…)."),
    "run_python": (
        PythonArgs,
        "Run a short Python calculation (sums, allocations, comparisons) and get its printed output.",
    ),
    "ask_user": (AskArgs, "Ask the player one question and stop."),
    "reply": (
        ReplyArgs,
        "Reply without new game facts and stop: greetings, cancel, unrelated requests, or questions about this "
        "conversation answered from recent_turns.",
    ),
    "finish": (FinishArgs, "Stop; the answer is written from the chosen evidence."),
}


def tool_specs(*, web: bool, ask: bool = True) -> list[dict]:
    skip = set()
    if not web:
        skip.add("search_web")
    if not ask:
        skip.add("ask_user")
    return [
        {"type": "function", "function": {"name": name, "description": doc, "parameters": model.model_json_schema()}}
        for name, (model, doc) in TOOLS.items()
        if name not in skip
    ]


def _preview(hit) -> dict:
    p = hit.payload
    return {
        "id": hit.id,
        "title": p.get("title"),
        "section": p.get("section"),
        "origin": "web" if isinstance(hit, WebHit) else "corpus",
        **{k: p[k] for k in ("source_type", "game_scope", "patch_version") if p.get(k) is not None},
        "text": p["text"][:PREVIEW_CHARS],
        "truncated": len(p["text"]) > PREVIEW_CHARS,
    }


def _web_results(found) -> list[dict]:
    """Các khối web nhóm theo trang, theo thứ tự trên trang, kèm bản xem trước ngắn; Agent tự mở khối cần."""
    pages: dict[str, dict] = {}
    for h in found:
        page = pages.setdefault(
            h.payload["url"], {"url": h.payload["url"], "title": h.payload.get("title"), "blocks": []}
        )
        page["blocks"].append({"id": h.id, "section": h.payload.get("section"), "text": h.payload["text"][:200]})
    return list(pages.values())


def working_state(state: dict) -> tuple[dict, dict | None]:
    """Working state của hội thoại nếu còn hiệu lực, và câu hỏi lại đang chờ (nếu có)."""
    req = state["req"]
    working = state.get("player") if isinstance(state.get("player"), dict) else {}
    if req.channel == "discord" and (req.external_ref or "").startswith("discord:thread:"):
        working = {}  # Transport dùng chung thread không có danh tính người gửi đã xác minh.
    if time.time() - working.get("updated", 0) > STATE_TTL_SECONDS:
        working = {}
    pending = working.get("pending")
    if pending and datetime.fromisoformat(pending["expires_at"]).timestamp() <= time.time():
        working, pending = {}, None
    if req.clarification_id and (not pending or str(req.clarification_id) != pending["id"]):
        from core.errors import BadRequestError

        raise BadRequestError("Câu hỏi bổ sung đã hết hạn hoặc không thuộc hội thoại này.")
    return working, pending


async def run_agent(pipe, state: dict) -> dict:
    """Điền state chuẩn bị: evidence, điều kiện, câu hỏi lại hoặc một reply tĩnh."""
    from app.rag.pipeline import context_item

    p, req = state["prepared"], state["req"]
    trace = p.trace
    working, pending = working_state(state)
    replying = bool(req.clarification_id and pending)
    conditions = {c["key"]: dict(c) for c in working.get("constraints", [])}
    memories = state.get("memory_candidates", [])
    sources = {"current": req.message, **{m["source_id"]: m["text"] for m in memories}}
    # Một ký ức có thể được gọi bằng row ID; điều kiện được lưu cùng tin nhắn người dùng sinh ra nó.
    aliases = {m["id"]: m["source_id"] for m in memories if m.get("id") and m["id"] != m["source_id"]}
    for row_id, source_id in aliases.items():
        sources.setdefault(row_id, sources[source_id])
    for c in conditions.values():
        if c["source_id"] != "current":
            sources.setdefault(c["source_id"], c["value"])
    if replying:
        sources["request"] = working.get("request_text", "")
    rounds = working.get("clarification_rounds", 0) if replying else 0
    limit = pipe.settings.chat_clarification_max_rounds
    can_ask = limit is None or rounds < limit
    web = state["search_mode"] != "off" and pipe.web_search is not None
    hits: dict = {}
    # Quy tắc level có nguồn (tổng chỉ số = level + 79) luôn sẵn để trích dẫn; nó không bao giờ được thêm vào câu trả
    # lời trừ khi Agent chọn.
    rule_hit = level_rule()
    hits[rule_hit.id] = rule_hit

    def gathered() -> list[str]:
        """Evidence Agent thực sự tìm được (quy tắc dựng sẵn không tính)."""
        return [i for i in hits if i != rule_hit.id]

    web_calls = local_ok = local_failed = 0
    reminded = {"evidence": False}
    retired: set[str] = set()
    started = time.perf_counter()
    deadline = state.get("started", started) + pipe.settings.prepare_budget_seconds
    # Web auto giữ ngân sách lớn hơn; các chế độ khác dùng ngân sách Agent mỗi lượt. Đếm lượt gọi model (không đếm số
    # tool trong một lượt); lượt cuối chỉ cho finish để Agent luôn tự chọn evidence và kết quả (23/11).
    max_calls = (
        pipe.settings.chat_coverage_max_calls
        if state.get("verify_coverage") or pipe.settings.chat_agent_max_calls is None
        else pipe.settings.chat_agent_max_calls
    )
    trace["agent"] = {"status": "running", "steps": []}
    trace["web_search"]["status"] = "not_run"

    def active_profile() -> dict:
        """Điều kiện của lượt này, kèm các khóa Agent chỉ giả định (đã nói với người chơi, không bao giờ lưu)."""
        profile = {k: c["value"] for k, c in conditions.items()}
        assumed = sorted(k for k, c in conditions.items() if c["source_id"] == ASSUMPTION)
        return {**profile, "assumed": ",".join(assumed)} if assumed else profile

    payload = {
        "player_message": req.message,
        **(
            {
                "replying_to": {
                    "id": pending["id"],
                    "question": pending["question"],
                    "original_request": working.get("request_text"),
                }
            }
            if replying
            else {}
        ),
        "conditions": list(conditions.values()),
        "memories": [{k: m[k] for k in ("id", "source_id", "text", "kind") if k in m} for m in memories],
        "recent_turns": state.get("recent_turns", []),
        "requested_language": req.options.lang,
        "web_policy": state["search_mode"] if web else "off",
        "built_in_sources": [
            {"id": rule_hit.id, "title": rule_hit.payload.get("title"), "text": rule_hit.payload["text"]}
        ],
        "can_ask_user": can_ask,
        "model_calls": max_calls,
    }
    messages = [SystemMessage(prompt("true_agent")), HumanMessage(json.dumps(payload, ensure_ascii=False))]
    # Thử nghiệm thinking cho Agent (23/11, mặc định tắt): DeepSeek không dùng temperature khi thinking, và
    # reasoning_content được adapter gửi lại ở mọi lượt sau.
    agent_thinking = pipe.settings.chat_agent_thinking
    trace["agent"]["thinking"] = agent_thinking
    bound = pipe.llm.model.bind_tools(
        tool_specs(web=web, ask=can_ask),
        tool_choice="auto",
        **(
            {"max_tokens": 8192, "reasoning_effort": "low", "extra_body": {"thinking": {"type": "enabled"}}}
            if agent_thinking
            else {"max_tokens": 4096, "temperature": 0, "extra_body": {"thinking": {"type": "disabled"}}}
        ),
    )

    def admit(found) -> list:
        new = []
        for h in found:
            ok = (
                state["search_mode"] != "off"
                if isinstance(h, WebHit)
                else pipe.policy.exclusion_reason(h.payload) is None
            )
            if ok:
                hits[h.id] = h
                new.append(h)
        return new

    async def local(query: str) -> list:
        nonlocal local_ok, local_failed
        local_failed += 1  # Được tính là thành công ở dưới khi retriever đã trả lời.
        retriever = pipe.retriever.model_copy(
            update={"limit": pipe.settings.rag_prefetch, "search_timeout_seconds": 5, "rerank_deadline": deadline}
        )
        async with asyncio.timeout(5 + getattr(retriever, "reranker_timeout_seconds", 0) + 0.1):
            docs = await retriever.ainvoke(query)
        local_failed, local_ok = local_failed - 1, local_ok + 1
        found = [document_to_hit(d) for d in docs[: pipe.settings.rag_prefetch]]
        # ID/điểm retrieval cho mỗi lần tìm local, phục vụ trace gỡ lỗi (không phải khẳng định về độ liên quan).
        trace.setdefault("retrieved", []).extend(
            {"id": h.id, "score": h.score, "title": h.payload.get("title"), "url": h.payload.get("url")} for h in found
        )
        return found

    def stated(c: Condition) -> bool:
        if c.source_id == ASSUMPTION:
            # Giả định lấp chỗ trống; nó không bao giờ được thay lời người chơi đã nói.
            current = conditions.get(c.key)
            return current is None or current["source_id"] == ASSUMPTION
        text = sources.get(c.source_id)
        return text is not None and (contains_text(text, c.value) or contains_name(text, c.value))

    async def execute(name: str, raw: dict):
        """(kết quả cho model, kết cục cuối hoặc None)."""
        nonlocal web_calls
        if (
            name not in TOOLS
            or (name == "search_web" and not web)
            or (name == "ask_user" and not can_ask)
            or (forced and name != "finish")
        ):
            return {"status": "error", "error": f"Tool {name} is not available"}, None
        try:
            args = TOOLS[name][0].model_validate(raw)
        except ValidationError as exc:
            fields = [".".join(map(str, e["loc"])) + ": " + e["type"] for e in exc.errors(include_input=False)][:5]
            return {"status": "error", "error": "Invalid arguments", "fields": fields}, None
        if name == "search_corpus":
            found = admit(await local(args.query))
            return {"status": "ok", "results": [_preview(h) for h in found[:RESULTS_PER_SEARCH]]}, None
        if name == "search_web":
            web_calls += 1
            try:
                found, diagnostic = await pipe.web_search.search(args.query)
            except WebSearchError as exc:
                trace["web_search"].update(status="error", reason=getattr(exc, "reason", type(exc).__name__))
                return {"status": "error", "error": "Web search failed"}, None
            trace["web_search"].update(status="ok", trigger="agent_tool", **diagnostic)
            return {"status": "ok", "pages": _web_results(admit(found))}, None
        if name == "check_name":
            found = admit(await local(args.name))
            matches, close = matching_names(args.name, found)
            return {
                "status": "ok",
                "candidates": [title for title, _ in matches][:5],
                "single_close_match": close and len(matches) == 1,
                "results": [_preview(h) for h in found[:RESULTS_PER_SEARCH]],
            }, None
        if name == "open_evidence":
            unknown = [i for i in args.ids if i not in hits]
            if unknown:
                return {"status": "error", "error": "Unknown evidence IDs", "ids": unknown}, None
            return {
                "status": "ok",
                "evidence": [{**context_item(hits[i], n), "id": i} for n, i in enumerate(args.ids, 1)],
            }, None
        if name == "set_conditions":
            # Chỉ kiểm nguồn gốc: mỗi giá trị phải xuất hiện trong nguồn nó ghi (lời người chơi hoặc ký ức).
            rejected = [c for c in args.set if not stated(c)]
            if rejected:
                # Hai lỗi khác nhau, nói riêng từng lỗi để Agent sửa đúng ngay lần sau (23/11).
                over = [c.key for c in rejected if c.source_id == ASSUMPTION]
                unquoted = [c.key for c in rejected if c.source_id != ASSUMPTION]
                problems = []
                if unquoted:
                    problems.append(
                        f"{', '.join(unquoted)}: the value must appear word for word in the named source (copy the "
                        "player's exact words, or leave the key out)"
                    )
                if over:
                    problems.append(
                        f"{', '.join(over)}: the player already stated this; an assumption cannot replace it"
                    )
                return {"status": "error", "error": "; ".join(problems), "keys": [c.key for c in rejected]}, None
            for key in args.retire:
                if conditions.pop(key, None) is not None:
                    retired.add(key)
            for c in args.set:
                row = c.model_dump()
                if row["source_id"] in aliases:
                    row["source_id"] = aliases[row["source_id"]]
                    trace["agent"]["normalized_source_refs"] = trace["agent"].get("normalized_source_refs", 0) + 1
                conditions[c.key] = row
            return {"status": "ok", "conditions": list(conditions.values())}, None
        if name == "run_python":
            # Phép tính riêng của Agent (22/11: thay calculator build viết cứng); chạy trong tiến trình riêng.
            return await asyncio.to_thread(run_python, args.code), None
        if name == "finish" and state["search_mode"] == "always" and not web_calls and web:
            return {"status": "error", "error": "Web policy is always: call search_web before finish"}, None
        if name == "finish" and not args.evidence_ids and gathered() and not reminded["evidence"]:
            # 22/11: server không còn dự phòng bằng mọi thứ tìm được; Agent được nhắc chọn một lần.
            reminded["evidence"] = True
            return {
                "status": "error",
                "error": "evidence_ids is empty: choose the evidence that supports the answer, "
                "or send finish again with no evidence_ids if none of it does",
            }, None
        return {"status": "ok"}, (name, args)

    outcome = None
    calls = 0
    forced = False

    async def call_model(model):
        nonlocal calls
        calls += 1
        trace.setdefault("model_calls", []).append({"phase": "agent"})
        async with asyncio.timeout(pipe.settings.chat_agent_timeout_seconds):
            return await model.ainvoke(messages)

    async def handle(ai):
        """Ghi usage và chạy các tool của một lượt; trả về kết cục cuối hoặc None."""
        usage = ai.usage_metadata or {}
        # Cùng khóa với usage của bước sinh, để token_usage() và trace đã lưu cũng đếm cả Agent.
        agent_usage = trace["agent"].setdefault("usage", {"prompt_tokens": 0, "completion_tokens": 0})
        agent_usage["prompt_tokens"] += usage.get("input_tokens") or 0
        agent_usage["completion_tokens"] += usage.get("output_tokens") or 0
        reasoning = (usage.get("output_token_details") or {}).get("reasoning") or 0
        if reasoning:
            agent_usage["reasoning_tokens"] = agent_usage.get("reasoning_tokens", 0) + reasoning
        messages.append(ai)
        # Lời gọi có tham số không phải JSON hợp lệ rơi vào invalid_tool_calls; mọi call ID đều cần một phản hồi.
        for bad in ai.invalid_tool_calls:
            trace["agent"]["steps"].append({"tool": bad.get("name") or "?", "status": "invalid_arguments"})
            messages.append(
                ToolMessage(
                    json.dumps({"status": "error", "error": "Arguments were not valid JSON; send the call again"}),
                    tool_call_id=bad["id"],
                )
            )
        if not ai.tool_calls:
            if not ai.invalid_tool_calls:
                messages.append(HumanMessage("Call a tool; end with finish, ask_user or reply, not plain text."))
            return None
        for call in ai.tool_calls:
            t0 = time.perf_counter()
            try:
                result, terminal = await execute(call["name"], call.get("args") or {})
            except (UnavailableError, TimeoutError, LLMError, WebSearchError) as exc:
                result, terminal = {"status": "error", "error": type(exc).__name__}, None
            step = {
                "tool": call["name"],
                "status": result.get("status"),
                "ms": round((time.perf_counter() - t0) * 1000),
            }
            if result.get("status") == "error":
                # Thông báo từ chối của chính server (không có output của model), để chẩn đoán được bước lỗi.
                step["error"] = str(result.get("error", ""))[:160]
                if result.get("keys") or result.get("fields"):
                    step["fields"] = result.get("keys") or result.get("fields")
            trace["agent"]["steps"].append(step)
            messages.append(ToolMessage(json.dumps(result, ensure_ascii=False), tool_call_id=call["id"]))
            if terminal is not None:
                # Các lời gọi còn lại của tin nhắn này không có phản hồi: vòng lặp kết thúc ở đây, sau chúng không gửi
                # gì nữa.
                return terminal
        return None

    while outcome is None:
        if calls >= max_calls - 1 or (time.perf_counter() > deadline and calls):
            # Hết lượt tìm hoặc hết thời gian: lượt cuối (bên dưới) chỉ cho finish.
            forced = True
            break
        left = max_calls - calls
        if calls > 0 and left <= 3:
            messages.append(
                HumanMessage(
                    f"{left} model calls left; the last one only allows finish. Stop searching: compute what you "
                    "still need, then call finish with the evidence and results you have."
                )
            )
        try:
            ai = await call_model(bound)
        except TimeoutError:
            if gathered():
                break
            raise UnavailableError("Bước Agent vượt thời gian xử lý.") from None
        except Exception as exc:  # noqa: BLE001 - provider failure; answer from evidence when there is some
            logger.warning("Agent model error", extra={"data": {"error": type(exc).__name__}})
            if gathered():
                break
            raise UpstreamError("Dịch vụ mô hình đang gặp sự cố. Vui lòng thử lại.") from None
        outcome = await handle(ai)

    if outcome is None and forced:
        # Lượt cuối chỉ có finish: Agent tự chọn evidence và ghi kết quả đã tính, thay vì mất hết những gì đã làm.
        reminded["evidence"] = True
        messages.append(
            HumanMessage("Budget exhausted: call finish now with the evidence IDs and results you already have.")
        )
        trace["agent"]["forced_finish"] = True
        try:
            final = pipe.llm.model.bind_tools(
                [s for s in tool_specs(web=web, ask=False) if s["function"]["name"] == "finish"],
                tool_choice="finish",
                max_tokens=4096,
                temperature=0,
                extra_body={"thinking": {"type": "disabled"}},
            )
            outcome = await handle(await call_model(final))
        except Exception as exc:  # noqa: BLE001 - như lượt thường: không có finish thì trả lời từ những gì có
            logger.warning("Agent final finish error", extra={"data": {"error": type(exc).__name__}})

    if outcome is None and calls and not any(s["status"] == "ok" for s in trace["agent"]["steps"]):
        # Model không tạo được lời gọi tool dùng được: lỗi provider, không phải câu trả lời rỗng "không có thông tin".
        trace["agent"]["status"] = "invalid_decision"
        raise UpstreamError("Mô hình chưa trả quyết định hợp lệ. Vui lòng thử lại.")
    trace["agent"].update(status="ok" if outcome else "budget", model_calls=calls)
    trace["tool_stop"] = outcome[0] if outcome else "model_budget"
    # Phần dành cho bước viết câu trả lời: sinh, một lần sửa định dạng, Answer Guard và chọn ảnh.
    p.max_calls = len(trace.get("model_calls", [])) + 4
    name, args = outcome if outcome else ("finish", None)
    if req.options.lang == "auto":
        # Ngôn ngữ Agent khai báo; nếu chưa khai báo thì ngôn ngữ của hội thoại, không thì tiếng Việt.
        lang = getattr(args, "answer_language", None) or working.get("lang") or "vi"
        p.lang = state["answer_language"] = lang
    action = {"ask_user": "clarify", "reply": "respond"}.get(name, "retrieve")
    if name == "reply":
        intent = (
            "cancel"
            if args.end_task
            else "out_of_scope"
            if args.unrelated
            else "conversation"
            if args.about_conversation
            else "smalltalk"
        )
    else:
        intent = getattr(args, "intent", None) or "other"
    request = getattr(args, "request", None) or (working.get("request_text") if replying else None) or req.message
    p.agent_decision = {"action": action, "intent": intent, "resolved_question": request}
    trace["agent"].update(action=action, intent=intent)
    trace["memory"]["selected_ids"] = sorted(
        {c["source_id"] for c in conditions.values() if c["source_id"] not in {"current", "request", ASSUMPTION}}
    )
    # Giả định chỉ ảnh hưởng câu trả lời lượt này; state đã lưu (và ký ức dữ kiện của nó) giữ dữ kiện của người chơi.
    state["turn_profile"] = active_profile()
    p.player_state = {
        "constraints": [c for c in conditions.values() if c["source_id"] != ASSUMPTION],
        "original": working.get("original", req.message) if replying else req.message,
        "request_text": working.get("request_text", req.message) if replying else req.message,
        "clarification_rounds": rounds + int(name == "ask_user"),
        "intent": intent,
        "lang": p.lang,
        "pending": None,
        "updated": time.time(),
        **({"retired_condition_keys": sorted(retired)} if retired else {}),
    }
    if intent == "cancel":
        p.player_state = {"updated": time.time(), "constraints": [], "pending": None}
    state["next_player"] = p.player_state
    state["history"] = []
    state["resolved_question"] = request
    trace["rewritten_query"] = request
    state["overview"] = intent == "overview"
    if state["overview"]:
        trace["request_kind"] = "overview"
    if name == "ask_user":
        p.clarification = Clarification(
            id=uuid4(),
            question=args.question,
            fields=[ClarificationField(key=m.key, label=m.label) for m in args.missing],
            expires_at=datetime.fromtimestamp(time.time() + STATE_TTL_SECONDS, UTC).isoformat(),
        )
        p.player_state["pending"] = p.clarification.model_dump(mode="json")
        p.static_answer = args.question
    elif name == "reply":
        p.static_answer = args.text
    else:
        p.gameplay_advice = bool(args and args.gameplay_advice)
        # Chỉ để chẩn đoán: bước viết có nhận được chính sách hay không.
        trace["agent"]["gameplay_advice"] = p.gameplay_advice
        p.reasoning = bool(args and args.needs_reasoning)
        trace["agent"]["needs_reasoning"] = p.reasoning
        chosen = [i for i in (args.evidence_ids if args else []) if i in hits]
        found = gathered()
        trace["evidence_selection"] = {"method": "model", "ids": chosen}
        state["agent_results"] = args.results if args else ""
        if not found and local_failed and not local_ok and not p.gameplay_advice:
            # Chính corpus không dùng được: lỗi dịch vụ, không phải câu trả lời rỗng "không có thông tin".
            raise UnavailableError("Kho tri thức chưa sẵn sàng.")
        if web and state["search_mode"] == "always" and not web_calls and not found:
            raise UnavailableError("Agent chưa hoàn tất tìm web bắt buộc trong ngân sách.")
    if rule_hit.id not in trace.get("evidence_selection", {}).get("ids", []):
        hits.pop(rule_hit.id, None)  # Không được chọn: không thuộc evidence của lượt này.
    state["documents"] = [hit_to_document(h) for h in hits.values() if not isinstance(h, WebHit)]
    state["web_hits"] = [h for h in hits.values() if isinstance(h, WebHit)]
    return state
