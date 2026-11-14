import pytest

from app.rag.agent import AgentDecision, DecisionError, check_decision
from tests.unit.test_agent_durable import AgentLLM, plan, req, service
from tests.unit.test_agent_durable import repo as repository_fixture  # noqa: F401
from tests.unit.test_tool_agent import ToolsLLM, step


def condition(key, value, source_id="current"):
    return {"key": key, "value": value, "source_id": source_id}


def correction(query, *conditions, superseded=(), intent="build"):
    return plan(
        intent=intent,
        turn_type="correction",
        entities=[],
        resolved_question=query,
        search_query=query,
        constraints=list(conditions),
        superseded_constraints=list(superseded),
    )


@pytest.mark.parametrize(
    ("key", "old", "new", "query"),
    [
        ("level", "90", "70", "Reduvia build level 70 or 90"),
        ("weapon", "Reduvia", "Moonveil", "Moonveil or Reduvia build"),
        ("starting_class", "Samurai", "Bandit", "Bandit or Samurai overlap"),
        ("goal", "PvE", "PvP", "PvE or PvP duels"),
        ("patch", "1.08", "1.10", "patch 1.10 or 1.08"),
        ("progress", "Stormveil Castle", "Liurnia", "Liurnia or Stormveil Castle progression"),
    ],
)
def test_replaced_conditions_do_not_pass_via_old_request(key, old, new, query):
    d = AgentDecision.model_validate(correction(query, condition(key, new)))
    with pytest.raises(DecisionError, match="superseded"):
        check_decision(d, new, [], {"request_text": old, "constraints": [condition(key, old, "request")]})


def test_agent_can_drop_an_old_value_that_only_occurs_in_original_request():
    old = condition("level", "90", "request")
    query = "Reduvia build level 70"
    d = correction(query, condition("level", "70"), superseded=[old])
    d["entities"] = ["Reduvia"]
    working = {"request_text": "Reduvia build level 90"}
    check_decision(AgentDecision.model_validate(d), "Đổi level 90 thành 70", [], working)
    d["search_query"] += " or 90"
    with pytest.raises(DecisionError, match="superseded"):
        check_decision(AgentDecision.model_validate(d), "Đổi level 90 thành 70", [], working)


def test_comparison_and_other_numeric_units_remain_available():
    working = {"request_text": "Reduvia level 90", "inactive_conditions": [condition("level", "90", "request")]}
    d = correction("Compare Reduvia level 70 and 90", intent="gameplay_comparison")
    d["entities"] = ["Reduvia"]
    check_decision(AgentDecision.model_validate(d), "So sánh level 70 và 90", [], working)
    d = correction("Reduvia level 70 attack power 90", condition("level", "70"))
    d["entities"] = ["Reduvia"]
    check_decision(AgentDecision.model_validate(d), "level 70, attack power 90", [], working)


def test_correction_can_name_the_mode_it_replaces():
    old = condition("goal", "PvE", "request")
    d = correction("Reduvia PvP build", condition("goal", "PvP"))
    d["entities"] = ["Reduvia"]
    check_decision(
        AgentDecision.model_validate(d),
        "Đổi từ PvE sang PvP",
        [],
        {"request_text": "Reduvia PvE", "constraints": [old]},
    )


def test_removal_does_not_force_old_weapon_into_query_as_a_negation():
    old = condition("weapon", "Reduvia", "request")
    d = correction("Bandit Great Knife PvE build", condition("weapon", "Great Knife"), superseded=[old])
    d["entities"] = ["Great Knife", "Bandit"]
    working = {"request_text": "Bandit Reduvia PvE build", "constraints": [old]}
    check_decision(AgentDecision.model_validate(d), "Không dùng Reduvia nữa, đổi sang Great Knife", [], working)
    with pytest.raises(DecisionError, match="Negation dropped"):
        check_decision(
            AgentDecision.model_validate(d), "Không dùng Reduvia nữa, đổi sang Great Knife, không dùng bùa", [], working
        )


async def test_model_repairs_stale_search_and_tool_uses_only_active_profile():
    first = plan(
        intent="build",
        action="clarify",
        entities=["Reduvia"],
        reply="Bạn chơi PvE hay PvP?",
        reason="missing_player_details",
        missing=[{"key": "goal", "label": "Mục tiêu"}],
        constraints=[condition("level", "90"), condition("weapon", "Reduvia"), condition("starting_class", "Bandit")],
        subgoals=["Allocate stats at level 90", "Explain the build"],
    )

    def resume(payload):
        working = payload["working_state"]
        active = [c for c in working["constraints"] if c["key"] != "level"]
        active += [condition("level", "70"), condition("goal", "PvE")]
        query = "Reduvia Bandit level 70 PvE build"
        if "repair" in payload:
            assert payload["repair"]["reason"] == "superseded_constraint"
        else:
            query += " or 90"
        d = correction(query, *active)
        return {**d, "turn_type": "clarification_reply", "entities": ["Reduvia", "Bandit"]}

    llm = ToolsLLM(
        [
            step("local_search", "Reduvia level 90 build"),
            step("local_search", "Reduvia Bandit level 70 PvE build"),
            step("finish", evidence_ids=["1"]),
        ],
        [first, resume, resume],
    )
    live = service(llm=llm, chat_tool_agent_enabled=True)
    question = req("Build Reduvia cho Bandit level 90", options={"web_search": "off"})
    opened = await live.answer(question)
    result = await live.answer(
        req(
            "PvE và đổi sang level 70",
            conversation_id=opened.conversation_id,
            clarification_id=opened.clarification.id,
            options={"web_search": "off"},
        )
    )
    trace = live.traces[result.message_id]
    assert result.grounded and trace["updated_condition_keys"] == ["level"]
    assert trace["tool_actions"][0]["status"] == "denied"
    assert live.pipeline.retriever.calls == [("Reduvia Bandit level 70 PvE build", True)]
    assert llm.observations[0]["task_plan"] == []
    assert llm.observations[0]["player_profile"] == {
        "level": "70",
        "weapon": "Reduvia",
        "starting_class": "Bandit",
        "goal": "PvE",
    }
    generator_input = llm.seen[-1][-1]["content"]
    assert '"level": "70"' in generator_input and "level 90" not in generator_input


async def test_removed_condition_stays_inactive_and_user_can_confirm_it_again():
    old = condition("patch", "1.08", "request")
    working = {"request_text": "Reduvia patch 1.08", "inactive_conditions": [old]}
    stale = correction("Reduvia patch 1.08", old)
    stale["turn_type"] = "followup"
    stale["entities"] = ["Reduvia"]
    with pytest.raises(DecisionError, match="active conditions"):
        check_decision(AgentDecision.model_validate(stale), "còn Reduvia thì sao", [], working)
    fresh = {**stale, "constraints": [condition("patch", "1.08")]}
    check_decision(AgentDecision.model_validate(fresh), "dùng lại patch 1.08", [], working)


async def test_live_switch_replay_identifies_stale_field_after_partial_repair():
    first = plan(
        intent="build",
        entities=["Reduvia", "Bandit"],
        resolved_question="Reduvia Bandit level 70 one-handed PvE build",
        search_query="Reduvia Bandit level 70 one-handed PvE build",
        constraints=[
            condition("starting_class", "Bandit"),
            condition("level", "70"),
            condition("weapon", "Reduvia"),
            condition("goal", "PvE"),
        ],
    )
    active_query = "Great Knife Bandit level 70 one-handed PvP build"
    current = [condition("weapon", "Great Knife"), condition("goal", "PvP")]

    def switch(payload):
        return correction(
            active_query,
            *[c for c in payload["working_state"]["constraints"] if c["key"] in {"starting_class", "level"}],
            *current,
            superseded=[condition("weapon", "Reduvia", "request"), condition("goal", "PvE", "request")],
        ) | {"entities": ["Great Knife", "Bandit"], "turn_type": "followup"}

    def original(payload):
        return switch(payload) | {
            "entities": ["Great Knife", "Reduvia", "Bandit"],
            "resolved_question": active_query + " instead of Reduvia, switching from PvE",
            "search_query": active_query + " instead of Reduvia",
        }

    def partial_repair(payload):
        assert "entities and goals" in payload["repair"]["validation_error"]
        return switch(payload) | {"resolved_question": active_query + " instead of Reduvia, switching from PvE"}

    def final_repair(payload):
        assert "resolved_question" in payload["repair"]["validation_error"]
        return switch(payload)

    live = service(llm=AgentLLM([first, original, partial_repair, final_repair]), chat_agent_max_calls=None)
    initial = await live.answer(req("Build Reduvia một tay cho Bandit level 70, PvE"))
    result = await live.answer(
        req(
            "Chuyển từ PvE sang PvP, dùng Great Knife thay cho Reduvia. Giữ class và level.",
            conversation_id=initial.conversation_id,
        )
    )
    trace = live.traces[result.message_id]
    assert trace["updated_condition_keys"] == ["goal", "weapon"]
    assert trace["agent"]["repair_attempts"] == 2
    assert live.pipeline.retriever.calls[-1] == (active_query, True)


async def test_live_comparison_replay_repairs_duplicate_profile_keys():
    comparison = "Compare Great Knife Bandit PvP builds at level 70 and 90"
    shared = [condition("weapon", "Great Knife"), condition("starting_class", "Bandit"), condition("goal", "PvP")]
    d = correction(comparison, *shared) | {"entities": ["Great Knife", "Bandit"], "turn_type": "new"}
    bad = d | {
        "constraints": [*shared, condition("level", "70"), condition("level", "90")],
        "superseded_constraints": [condition("level", "70", "request")],
    }

    def repair(payload):
        issue = payload["repair"]["validation_error"][0]
        assert issue["type"] == "duplicate_constraint" and "omit that key" in issue["message"]
        return d | {"intent": "gameplay_comparison"}

    live = service(llm=AgentLLM([bad, bad, repair]), chat_agent_max_calls=None)
    result = await live.answer(req("So sánh Great Knife PvP cho Bandit ở level 70 và 90"))
    assert live.traces[result.message_id]["agent"]["repair_attempts"] == 2
    assert live.pipeline.retriever.calls == [(comparison, True)]


async def test_explicit_removal_survives_repository_reload(repository_fixture):  # noqa: F811
    repo = repository_fixture
    first = plan(
        intent="build",
        entities=["Reduvia"],
        resolved_question="Reduvia build patch 1.08",
        search_query="Reduvia build patch 1.08",
        constraints=[condition("patch", "1.08")],
    )
    remove = correction("Reduvia build", superseded=[condition("patch", "1.08", "request")])
    remove["entities"] = ["Reduvia"]
    live = service(repo=repo, llm=AgentLLM([first, remove]))
    initial = await live.answer(req("Build Reduvia ở patch 1.08"))
    result = await live.answer(
        req(
            "Không giới hạn patch nữa",
            conversation_id=initial.conversation_id,
            conversation_token=initial.conversation_token,
        )
    )
    saved = await repo.load(result.conversation_id, channel="web", external_ref=None, token=result.conversation_token)
    assert saved.working["constraints"] == []
    assert saved.working["inactive_conditions"] == [condition("patch", "1.08", "request")]
    assert not [r for r in await repo.memories(result.conversation_id) if r["kind"] == "fact"]
