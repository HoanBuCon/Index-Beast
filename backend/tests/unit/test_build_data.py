"""Allocation checks use synthetic requirement fixtures and the curated pack rules; not live factual claims."""

import copy
import json
import re
from contextlib import aclosing

import pytest

from app.rag.build_data import (
    ATTRIBUTES,
    bound_value,
    build_rules,
    check,
    level_rule,
)
from app.rag.generator import Prepared, RAGValidationError, validate_answer
from tests.unit.test_live_chat import hit


def n(value, label, source_id="1"):
    return {"value": value, "label": label, "source_id": source_id, "quote_id": "q0"}


def allocation(*values):
    return dict(zip(ATTRIBUTES, values, strict=True))


def rule_hits(_profile=None):
    """The pack snapshot a checked artifact always cites: the level accounting rule."""
    return [level_rule()[0]]


def infobox(level, *values):
    """Exact format of an origin Infobox chunk in the S5 corpus add-on (wiki.gg, 20/11/2026)."""
    lines = ["Information", "Stats", f"Attributes / Level: {level}"]
    extras = iter(
        ["Base Stats / HP: 414", "Base Stats / FP: 78", "Base Stats / Stamina: 96", "Base Stats / Equip Load: 48.2"]
    )
    for key, value in zip(ATTRIBUTES, values, strict=True):
        lines.append(f"Attributes / {key.title()}: {value}")
        if (extra := next(extras, None)) is not None:
            lines.append(extra)
    return "\n".join(lines)


def origin(name, source_id, level, *values):
    return {
        "name": name,
        "level": n(level, "Level", source_id),
        "base": {k: n(v, k.title(), source_id) for k, v in zip(ATTRIBUTES, values, strict=True)},
    }


WRETCH = (1, *([10] * 8))
VAGABOND = (9, 15, 10, 11, 14, 13, 9, 9, 7)
GREATSWORD = "Greatsword requirements (one-handed): Required Strength: 31. Required Dexterity: 12."


@pytest.fixture
def build():
    """Level 130 Greatsword, no class named: the planner quoted the default Wretch Infobox. Total 209."""
    weapon = hit(1, title="Greatsword", text=GREATSWORD, release_scope="unknown")
    wretch = hit("w", title="Wretch", section="Infobox", text=infobox(*WRETCH), release_scope="unknown")
    data = {
        "weapon": "Greatsword",
        "requirements": {"strength": n(31, "Required Strength"), "dexterity": n(12, "Required Dexterity")},
        "starting_class": origin("Wretch", "w", *WRETCH),
    }
    alloc = allocation(40, 15, 30, 60, 14, 10, 10, 30)  # 209 = 130 + 79
    profile = {"level": "130", "weapon": "Greatsword"}
    return data, alloc, profile, [weapon, wretch]


def test_pack_keeps_only_the_level_rule_for_builds():
    from app.rag.gameplay_knowledge import load_pack

    hit_, data = level_rule()
    assert f"minus {data['level_offset']}" in hit_.payload["text"]
    kinds = {row["payload"].get("rule_kind") for g in load_pack()["groups"] for row in g["hits"]}
    assert "class_rule" not in kinds  # Origins are corpus pages now; the agent quotes their Infobox.


def test_build_rules_give_the_planner_its_targets():
    rules = build_rules({"level": "level 95"})
    assert rules["attribute_total"] == 174 and rules["attribute_cap"] == 99
    assert rules["starting_class"] is None and rules["default_class"] == "Wretch"
    assert build_rules({"level": "100", "starting_class": "Vagabond"})["starting_class"] == "Vagabond"
    assert build_rules({}) is None


def test_sourced_requirements_and_quoted_default_class(build):
    result = check(*build)
    assert result["attribute_total"] == 209 and result["starting_class"] == "Wretch"
    assert result["class_assumed"] and result["class_floor_verified"] and result["requirements_checked"]
    assert not result["weapon_suggested"] and not result["optimality_verified"]
    assert result["sources"] == [level_rule()[0].id, "w", "1"]
    assert set(result["provenance"]) == set(result["sources"])


def test_allocation_without_any_weapon_or_class_is_still_checked_arithmetic():
    result = check({}, allocation(30, 20, 25, 10, 10, 10, 10, 10), {"level": "46"}, [])
    assert result["weapon"] is None and not result["requirements_checked"] and result["attribute_total"] == 125
    assert result["starting_class"] is None and not result["class_floor_verified"] and not result["class_assumed"]


def test_named_weapon_without_requirement_source_is_labelled_not_checked():
    result = check({}, allocation(30, 20, 25, 10, 10, 10, 10, 10), {"level": "46", "weapon": "Greatsword"}, [])
    assert result["weapon"] == "Greatsword" and not result["requirements_checked"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda a: a.update(vigor=41), "sums to 210; level 130 needs exactly 209"),
        (lambda a: a.update(strength=30, vigor=70), "strength 30 is below the Greatsword requirement 31"),
        (lambda a: a.update(mind=9, vigor=46), "mind 9 is below the Wretch starting value 10"),
        (lambda a: a.update(strength=100, vigor=0), "strength 100 exceeds 99"),
    ],
)
def test_rejections_tell_the_planner_exactly_what_to_fix(build, change, message):
    data, alloc, profile, hits = copy.deepcopy(build)
    change(alloc)
    with pytest.raises(ValueError, match=re.escape(message)):
        check(data, alloc, profile, hits)


def vagabond():
    page = hit("v", title="Vagabond", section="Infobox", text=infobox(*VAGABOND), release_scope="unknown")
    return {"starting_class": origin("Vagabond", "v", *VAGABOND)}, [page]


def test_named_class_uses_its_quoted_floors_and_level():
    data, hits = vagabond()
    profile = {"level": "100", "starting_class": "Vagabond"}
    ok = allocation(40, 10, 25, 14, 60, 9, 9, 12)  # 179 = 100 + 79
    result = check(data, ok, profile, hits)
    assert result["starting_class"] == "Vagabond" and result["class_floor_verified"] and not result["class_assumed"]
    with pytest.raises(ValueError, match="vigor 14 is below the Vagabond starting value 15"):
        check(data, {**ok, "vigor": 14, "dexterity": 86}, profile, hits)
    with pytest.raises(ValueError, match="below the Vagabond starting level 9"):
        check(data, ok, {"level": "5", "starting_class": "Vagabond"}, hits)


def test_named_class_not_quoted_keeps_arithmetic_and_reports_floors_unchecked():
    profile = {"level": "60", "starting_class": "Vagabond"}
    result = check({}, allocation(40, 15, 25, 20, 20, 9, 9, 1), profile, [])  # 139 = 60 + 79
    assert not result["class_floor_verified"] and not result["class_assumed"]
    assert result["starting_class"] == "Vagabond" and result["rule_sources"] == [level_rule()[0].id]


@pytest.mark.parametrize("error", ["other_class", "misread", "unbound", "page_names_other_class", "partial"])
def test_class_values_need_the_confirmed_class_and_its_own_page(error):
    data, hits = vagabond()
    profile = {"level": "100", "starting_class": "Vagabond"}
    ok = allocation(40, 10, 25, 14, 60, 9, 9, 12)
    if error == "other_class":
        data["starting_class"]["name"] = "Wretch"
    elif error == "misread":  # Vigor 16 is not on the page, and the values no longer sum to level + 79.
        data["starting_class"]["base"]["vigor"]["value"] = 16
        hits[0].payload["text"] = hits[0].payload["text"].replace("Vigor: 15", "Vigor: 16")
    elif error == "unbound":
        data["starting_class"]["base"]["arcane"]["value"] = 8
    elif error == "page_names_other_class":
        hits[0].payload["title"] = "Hero"
    else:
        data["starting_class"]["base"].pop("arcane")
    with pytest.raises(ValueError):
        check(data, ok, profile, hits)


@pytest.mark.parametrize(
    "error", ["weapon_mismatch", "unknown_source", "source_without_weapon", "requirements_without_weapon", "two_hand"]
)
def test_requirement_provenance_errors(build, error):
    data, alloc, profile, hits = copy.deepcopy(build)
    if error == "weapon_mismatch":
        data["weapon"] = "Zweihander"
    elif error == "unknown_source":
        data["requirements"]["strength"]["source_id"] = "unfetched"
    elif error == "source_without_weapon":
        hits[0].payload["title"] = "Claymore"
        hits[0].payload["text"] = GREATSWORD.replace("Greatsword", "Claymore")
    elif error == "requirements_without_weapon":
        data.pop("weapon")
        profile.pop("weapon")
    else:
        hits[0].payload["handedness"] = "two_handed"
    with pytest.raises(ValueError):
        check(data, alloc, profile, hits)


def test_suggested_weapon_is_marked(build):
    data, alloc, profile, hits = copy.deepcopy(build)
    profile.pop("weapon")
    assert check(data, alloc, profile, hits)["weapon_suggested"]


def test_headers_are_bound_to_values_and_correct_row():
    q = "| Class | Level | Vigor | Mind |\n| --- | --- | --- | --- |\n| Hero | 7 | 14 | 9 |\n| Vagabond | 9 | 15 | 10 |"
    assert bound_value(q, "Vigor", 15, entity="Vagabond")
    assert not bound_value(q, "Vigor", 10, entity="Vagabond")
    assert not bound_value(q, "Vigor", 14, entity="Vagabond")
    assert not bound_value("Vigor: 15, Mind: 10", "Vigor", 10)


def test_a_number_cannot_move_to_another_attribute(build):
    data, alloc, profile, hits = copy.deepcopy(build)
    # "Required Strength: 31" is Strength's number; filing it under Faith must fail even with that label.
    data["requirements"] = {"faith": data["requirements"]["strength"]}
    with pytest.raises(ValueError, match="faith 31 is not bound"):
        check(data, alloc, profile, hits)


def test_the_requirement_key_not_the_copied_label_decides_the_attribute(build):
    data, alloc, profile, hits = copy.deepcopy(build)
    data["requirements"]["strength"]["label"] = "Requirements"  # Copied a section header; the source still binds.
    assert check(data, alloc, profile, hits)["requirements_checked"]


SPELL_INFOBOX = "Type: Sorcery\nCategory: Cold Sorcery\nFP Cost: 17\nAttributes Required\nInt: 36, Fth: 0, Arc: 0"
STAFF_TABLE = (
    "Attributes\nAttribute | Required | Scaling\nStrength: | 6 | E\nDexterity:\nIntelligence: | 28 | B\nFaith:\nArcane:"
)


def real_format_build(text, requirements):
    """A requirement quote in the exact format of a local corpus chunk, level 95 Wretch."""
    source = hit(2, title="Equipment", text=text, release_scope="unknown")
    data = {"weapon": "Equipment", "requirements": {k: n(v, label, "2") for k, (v, label) in requirements.items()}}
    return data, allocation(40, 20, 20, 10, 10, 54, 10, 10), {"level": "95"}, [source]  # 174 = 95 + 79


@pytest.mark.parametrize(
    ("text", "requirements"),
    [
        # Live 20/11: the model copied the section header, the wiki abbreviates Faith as "Fth".
        (SPELL_INFOBOX, {"intelligence": (36, "Attributes Required"), "faith": (0, "Fth")}),
        # Row-oriented staff table: the number sits under the "Required" column of the Intelligence row.
        (STAFF_TABLE, {"intelligence": (28, "Required"), "strength": (6, "Strength")}),
    ],
)
def test_requirements_in_real_corpus_formats_are_accepted(text, requirements):
    assert check(*real_format_build(text, requirements))["attribute_total"] == 95 + 79


@pytest.mark.parametrize(
    ("text", "requirements"),
    [
        (SPELL_INFOBOX, {"intelligence": (17, "FP Cost")}),  # A number of a different field.
        (STAFF_TABLE, {"intelligence": (6, "Required")}),  # Strength's cell, not Intelligence's.
        (SPELL_INFOBOX, {"arcane": (36, "Int")}),  # Intelligence's number under another attribute.
    ],
)
def test_requirements_in_real_corpus_formats_still_need_the_right_attribute(text, requirements):
    with pytest.raises(ValueError, match="not bound"):
        check(*real_format_build(text, requirements))


@pytest.mark.parametrize(
    ("label", "ok"), [("Str Req", True), ("Required Str.", True), ("Str/Dex", False), ("Req", False)]
)
def test_requirement_headers_must_name_exactly_one_attribute(build, label, ok):
    data, alloc, profile, hits = copy.deepcopy(build)
    hits[0].payload["text"] = GREATSWORD.replace("Required Strength: 31", f"{label}: 31")
    data["requirements"]["strength"]["label"] = label
    if ok:
        check(data, alloc, profile, hits)
    else:
        with pytest.raises(ValueError):
            check(data, alloc, profile, hits)


def test_tavily_rendered_attribute_cell_keeps_header_value_binding():
    quote = (
        "| Attribute | Required | Scaling |\n| Image 20: ER Custom Stat Icon Strength (Color).pngStrength: | 5 | E |"
    )
    assert bound_value(quote, "Strength", 5)
    assert not bound_value(quote, "Strength", 20)
    assert not bound_value(quote, "Strength", 13)


@pytest.mark.parametrize("field", ["patch_version", "affinity", "upgrade_level"])
def test_requirement_sources_cannot_mix_explicit_variants(build, field):
    data, alloc, profile, hits = copy.deepcopy(build)
    hits.append(hit(2, title="Greatsword", text=GREATSWORD))
    hits[0].payload[field] = "first"
    hits[-1].payload[field] = "second"
    data["requirements"]["dexterity"]["source_id"] = "2"
    with pytest.raises(ValueError, match="Conflicting"):
        check(data, alloc, profile, hits)


def answer_with(p, text="Dồn điểm vào Strength vì Greatsword cần Strength cao [1]."):
    return validate_answer(p, {"answer": text, "evidence": [{"index": 1, "quote_id": "q0"}], "insufficient": False})


def test_generator_renders_table_label_and_cites_rule_sources(build):
    data, alloc, profile, hits = build
    artifact = check(*build)
    context = [*hits, *rule_hits(profile)]
    p = Prepared("rag", "vi", [], hits=context, checked_build=artifact, values={"player_profile": profile})
    out = answer_with(p)
    assert "Gợi ý phân bổ cho Greatsword (một tay, không bonus, giả định class Wretch vì bạn chưa nêu class)" in (
        out.answer
    )
    assert all(f"{k.title()} {v}" in out.answer for k, v in alloc.items())
    # The prose cited only the weapon; the backend cites the accounting and class snapshots itself.
    assert [s.index for s in out.sources] == [1, 2, 3] and out.answer.rstrip().endswith("[1][2][3]")
    with pytest.raises(RAGValidationError):
        validate_answer(
            p,
            {
                "answer": "Ok [1].",
                "evidence": [{"index": 1, "quote_id": "q0"}],
                "insufficient": False,
                "build_allocation": {**alloc, "vigor": 99},
            },
        )
    with pytest.raises(RAGValidationError):
        validate_answer(p, {"answer": "Thiếu dữ liệu.", "evidence": [], "insufficient": True})


@pytest.mark.parametrize(
    ("profile", "label"),
    [
        ({"level": "46"}, "Gợi ý phân bổ 8 chỉ số (chưa kiểm chỉ số khởi đầu của class, chưa chọn vũ khí"),
        ({"level": "46", "weapon": "Greatsword"}, "(một tay, không bonus, chưa kiểm chỉ số khởi đầu của class,"),
        ({"level": "60", "starting_class": "Vagabond"}, "chưa kiểm chỉ số khởi đầu của class Vagabond"),
    ],
)
def test_labels_state_every_assumption_and_unchecked_part(profile, label):
    alloc = (
        allocation(30, 20, 25, 10, 10, 10, 10, 10)
        if profile["level"] == "46"
        else (allocation(40, 15, 25, 20, 20, 9, 9, 1))
    )
    artifact = check({}, alloc, profile, [])
    context = [hit(1, title="Note", text="Strength scales Greatsword damage."), *rule_hits(profile)]
    p = Prepared("rag", "vi", [], hits=context, checked_build=artifact, values={"player_profile": profile})
    out = answer_with(p, "Ưu tiên Strength [1].")
    assert label in out.answer
    if profile.get("weapon"):
        assert "chưa kiểm yêu cầu vũ khí" in out.answer


@pytest.mark.parametrize("prose", ["Vigor 99 [1].", "| Vigor | Mind |\n| 99 | 99 | [1]"])
def test_different_stats_in_prose_ask_the_guard_and_show_the_checked_table(build, prose):
    """Policy 20/11/2026: wrong numbers are not a reason to drop the answer. Without a guard pass the checked
    table is appended with a note, and the Answer Guard is requested to fix the writer's own table."""
    profile = build[2]
    p = Prepared(
        "rag",
        "vi",
        [],
        hits=[*build[3], *rule_hits(profile)],
        checked_build=check(*build),
        values={"player_profile": profile},
    )
    out = answer_with(p, prose)
    assert "Vigor 40 | Mind 15" in out.answer and "đây là bảng đã kiểm" in out.answer
    assert p.trace["guard_request"]["issues"][0]["kind"] == "numbers"


async def prepare_with_profile(profile, hits, script, message):
    """Agent loop over the build fixture; the profile is kept from an earlier player message."""
    import time

    from app.rag.pipeline import ChatPipeline
    from tests.unit.test_agent_durable import settings
    from tests.unit.test_live_chat import FakeRetriever
    from tests.unit.test_true_agent import RecordingLLM, req

    llm = RecordingLLM(script)
    working = {
        "constraints": [{"key": k, "value": v, "source_id": "m1"} for k, v in profile.items()],
        "updated": time.time(),
    }
    p = await ChatPipeline(settings(), llm, FakeRetriever(hits)).prepare(req(message), [], player=working)
    return llm, p


async def test_tool_calculator_needs_only_level_and_cites_pack_rules(build):
    from tests.unit.test_true_agent import finish

    data, alloc, profile, hits = build
    script = [
        ("search_corpus", {"query": "Greatsword requirements"}),
        ("calculator", {"build_data": data, "allocation": alloc}),
        finish(intent="build", evidence_ids=["1"]),
    ]
    llm, p = await prepare_with_profile(profile, hits, script, "Chia chỉ số cho tôi.")
    # The level comes from the kept condition; the accounting rule is built in, not searched.
    assert llm.tool_result(2)["status"] == "ok" and llm.tool_result(2)["checked_build"]["allocation"] == alloc
    assert p.checked_build["allocation"] == alloc and p.trace["build_check"]["status"] == "checked"
    assert {h.id for h in p.hits} >= set(p.checked_build["sources"])
    assert json.loads(p.values["payload"])["checked_build"]["allocation"] == alloc


async def test_calculator_rejection_is_fed_back_to_the_agent(build):
    from tests.unit.test_true_agent import finish

    data, alloc, profile, hits = copy.deepcopy(build)
    wrong = {**alloc, "vigor": alloc["vigor"] + 1}
    script = [
        ("calculator", {"build_data": {}, "allocation": wrong}),
        ("calculator", {"build_data": {"weapon": "Greatsword"}, "allocation": wrong}),
        finish(intent="build"),
    ]
    llm, p = await prepare_with_profile(profile, hits, script, "Build")
    assert p.checked_build is None and "needs exactly 209" in llm.tool_result(1)["error"]
    assert p.trace["build_check"] == {
        "status": "failed",
        "failed_attempts": 2,
        "class_given": False,
        "weapon_given": True,
    }


@pytest.mark.parametrize(
    ("answer", "fields"),
    [
        ("Chưa có lớp xuất phát hoặc checked_build nên không thể chốt số điểm [1].", ["checked_build"]),
        ("Theo `player_profile`, ưu tiên Intelligence [1].", ["player_profile"]),
    ],
)
def test_internal_field_names_go_to_the_guard_and_are_never_shown(build, answer, fields):
    p = Prepared("rag", "vi", [], hits=build[3], values={"player_profile": build[2]})
    out = answer_with(p, answer)
    # Not dropped: the Answer Guard is asked to rewrite it, and the fallback answer already reads naturally.
    assert p.trace["guard_request"]["issues"] == [{"kind": "internal_field_name", "fields": fields}]
    assert not any(f in out.answer for f in fields) and "`" not in out.answer
    assert "bảng chia điểm đã kiểm" in out.answer or "thông tin bạn đưa ra" in out.answer
    clean = Prepared("rag", "vi", [], hits=build[3], values={"player_profile": build[2]})
    answer_with(clean, "Mình chưa kiểm chứng được bảng chia điểm chính xác từ nguồn; ưu tiên Strength [1].")
    assert "guard_request" not in clean.trace


async def test_every_answer_is_held_and_the_guard_rewrites_an_internal_field_name():
    from app.api.schemas.chat import ChatRequest
    from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, service

    evidence = '"evidence": [{"index": 1, "quote": "Ranni is an Empyrean"}], "insufficient": false}'
    leak = '{"answer": "Ranni là Empyrean [1].\\nThiếu checked_build nên chưa chia điểm [1]. ", ' + evidence
    llm = FakeLLM(tokens=[leak[:30], leak[30:]])
    llm.data = {"answer": "Ranni là Empyrean [1].\nMình chưa có bảng chia điểm đã kiểm nên chưa chia điểm [1]."}
    live = service(llm=llm, retriever=FakeRetriever(), rag_format_retries=0)
    async with aclosing(await live.open_stream(ChatRequest(**BODY))) as events:
        frames = [frame async for frame in events]
    tokens = [p.token for n, p in frames if n == "token"]
    # Shown once, after the check: nothing visible is cut or replaced by an error afterwards.
    assert frames[-1][0] == "done" and len(tokens) == 1
    assert "checked_build" not in tokens[0] and tokens[0].startswith(llm.data["answer"])


def test_unchecked_allocation_field_is_dropped_but_prose_numbers_are_a_reference(build):
    data, alloc, profile, hits = build
    p = Prepared("rag", "vi", [], hits=hits, values={"player_profile": profile})
    raw = {"answer": "Ưu tiên Strength [1].", "evidence": [{"index": 1, "quote_id": "q0"}], "insufficient": False}
    out = validate_answer(p, {**raw, "build_allocation": alloc})
    assert out.answer.startswith(raw["answer"]) and "chưa được công cụ tính kiểm tra" in out.answer
    assert not any(f"{k.title()} {v}" in out.answer for k, v in alloc.items())
    assert p.trace["dropped_unchecked_allocation"] is True
    # Prose numbers without a calculator are a reference suggestion: kept, not a failure.
    kept = validate_answer(p, {**raw, "answer": "Vigor 40, Strength 60 [1].", "build_allocation": alloc})
    assert "Vigor 40, Strength 60" in kept.answer


def test_fill_lets_the_calculator_do_the_arithmetic():
    data, hits = vagabond()
    profile = {"level": "100", "starting_class": "Vagabond"}  # 179 points
    result = check(data, {"vigor": 40, "endurance": 25}, profile, hits, fill="strength")
    # Unset attributes stay at the Vagabond floor; Strength takes exactly what is left.
    assert result["allocation"] == allocation(40, 10, 25, 66, 13, 9, 9, 7)
    assert sum(result["allocation"].values()) == 179


@pytest.mark.parametrize(
    ("targets", "fill", "message"),
    [
        ({"vigor": 99, "endurance": 99}, "strength", "below its starting value"),
        ({}, "strength", "over 99"),
        ({"vigor": 40}, "", "Give all eight attributes"),
        ({"vigor": 40}, "luck", "fill must be one of the eight attributes"),
    ],
)
def test_fill_rejections_say_what_to_change(targets, fill, message):
    data, hits = vagabond()
    with pytest.raises(ValueError, match=message):
        check(data, targets, {"level": "100", "starting_class": "Vagabond"}, hits, fill=fill)


def writer_table(alloc, wrong=None):
    rows = [f"| {k.title()} | {wrong if k == 'vigor' and wrong else v} | lý do |" for k, v in alloc.items()]
    return "\n".join(["| Chỉ số | Điểm | Lý do |", "|---|---|---|", *rows, "[1]"])


def checked_prepared(build):
    profile = build[2]
    return Prepared(
        "rag",
        "vi",
        [],
        hits=[*build[3], *rule_hits(profile)],
        checked_build=check(*build),
        values={"player_profile": profile},
    )


def test_writer_prints_the_checked_table_and_the_backend_only_adds_assumptions(build):
    p = checked_prepared(build)
    text = "Dồn Strength cho Greatsword (yêu cầu Strength 31) [1].\n\n" + writer_table(build[1])
    out = answer_with(p, text)
    assert "| Vigor | 40 |" in out.answer and p.trace["allocation_printed_by_writer"]
    assert "Vigor 40 | Mind 15" not in out.answer  # No duplicate numbers line.
    assert "giả định class Wretch" in out.answer


def test_assumption_note_sits_directly_under_the_writer_table(build):
    p = checked_prepared(build)
    table = writer_table(build[1])
    out = answer_with(p, "Dồn Strength cho Greatsword [1].\n\n" + table + "\n\nNâng Vigor trước khi lên boss khó [1].")
    head, tail = out.answer.split("Ghi chú cho bảng: ", 1)
    # Table, then the note (own paragraph, with the rule citations), then the writer's closing prose.
    assert head.rstrip().endswith(table.rstrip()) and "giả định class Wretch" in tail.split("\n")[0]
    assert tail.split("\n")[0].rstrip().endswith("[1][2][3]") and tail.endswith(
        "Nâng Vigor trước khi lên boss khó [1]."
    )


def test_class_starting_values_in_the_prose_do_not_count_as_the_table_total():
    from app.rag.generator import build_issues

    profile = {"level": "150", "starting_class": "Astrologer"}
    p = Prepared("rag", "vi", [], hits=[], values={"player_profile": profile})
    table = writer_table(allocation(50, 30, 20, 10, 14, 45, 50, 10))  # 229 = 150 + 79
    floors = "Astrologer khởi đầu với Vigor 9, Mind 15, Endurance 9, Strength 8, Dexterity 12, Intelligence 16, "
    answer = table + "\n\n" + floors + "Faith 7, Arcane 9 [1]."
    assert build_issues(p, answer) == []
    wrong = writer_table(allocation(50, 30, 20, 10, 14, 45, 50, 11)) + "\n\n" + floors + "Faith 7, Arcane 9 [1]."
    assert build_issues(p, wrong)[0]["printed_total"] == 230


def test_a_wrong_number_in_the_writer_table_requests_the_guard(build):
    p = checked_prepared(build)
    out = answer_with(p, "Bảng [1].\n\n" + writer_table(build[1], wrong=41))
    assert "| Vigor | 41 |" in out.answer and "Vigor 40 | Mind 15" in out.answer
    assert p.trace["guard_request"]["issues"] == [{"kind": "numbers", "pairs": [{"attribute": "vigor", "printed": 41}]}]


async def test_build_stream_is_held_until_the_guard_fixed_the_table(build):
    from app.rag.generator import Generator
    from tests.unit.test_live_chat import FakeLLM

    p = checked_prepared(build)
    p.template, p.values = (
        None,
        {**p.values, "policy": "", "persona": "", "lang": "vi", "spoilers": True, "history": [], "payload": "{}"},
    )
    evidence = '"evidence": [{"index": 1, "quote_id": "q0"}], "insufficient": false}'
    llm = FakeLLM(tokens=['{"answer": "Vigor 41 cho build này [1].\\n', 'Phần còn lại [1]. ", ' + evidence])
    fixed = "Bảng đã sửa [1].\n\n" + writer_table(build[1])
    llm.data = {"answer": fixed}  # What the Answer Guard returns (JSON call of the fake model).
    async with aclosing(Generator(llm, format_retries=0).stream(p)) as tokens:
        shown = [token async for token in tokens]
    # Nothing was shown before the guard: one chunk, already corrected, plus the assumptions line.
    assert len(shown) == 1 and shown[0].startswith(fixed) and "Vigor 41" not in shown[0]
    assert p.trace["answer_guard"]["status"] == "applied"


def test_fill_without_quoted_class_floors_is_refused():
    with pytest.raises(ValueError, match="Quote the starting class Infobox"):
        check({}, {"vigor": 40}, {"level": "100"}, [], fill="strength")


def test_class_name_may_be_omitted_and_defaults_to_the_users_class():
    data, hits = vagabond()
    data["starting_class"].pop("name")
    result = check(data, {"vigor": 40}, {"level": "100", "starting_class": "Vagabond"}, hits, fill="strength")
    assert result["starting_class"] == "Vagabond" and result["class_floor_verified"]
