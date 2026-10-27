"""Unit tests for agent planning, reflection, and delegation engines."""

from amberclaw.agent.planning.delegation import DelegationPlanner, SubTaskAssignment
from amberclaw.agent.planning.react import ReActPlanner
from amberclaw.agent.planning.reflection import ReflectionEngine


def test_reflection_engine_plan_evaluation():
    engine = ReflectionEngine(risk_threshold=0.6)

    # 1. Empty plan evaluation
    empty_critique = engine.evaluate_plan("Deploy update", [])
    assert empty_critique.is_viable is False
    assert empty_critique.risk_level == "critical"

    # 2. Safe multi-step plan
    safe_critique = engine.evaluate_plan(
        "Build docs",
        ["Run mkdocs build", "Verify HTML artifacts in site/ directory"],
    )
    assert safe_critique.is_viable is True
    assert safe_critique.risk_level == "low"
    assert safe_critique.confidence >= 0.9

    # 3. Risky / destructive plan
    risky_critique = engine.evaluate_plan(
        "Clean filesystem",
        ["rm -rf /data/workspace", "Recreate folder"],
    )
    assert risky_critique.risk_level == "high"
    assert any("destructive" in w for w in risky_critique.weaknesses)


def test_reflection_engine_action_critique():
    engine = ReflectionEngine()

    # Success case
    ok_critique = engine.critique_action_result("run_command", "Build succeeded. 0 errors.")
    assert ok_critique.is_viable is True
    assert ok_critique.risk_level == "low"

    # Failure / error case
    err_critique = engine.critique_action_result("run_command", "PermissionDenied: Access denied to /root")
    assert err_critique.is_viable is False
    assert err_critique.risk_level == "medium"
    assert len(err_critique.suggestions) > 0


def test_delegation_planner_dag_execution():
    planner = DelegationPlanner()

    t1 = SubTaskAssignment(subtask_id="t1", title="Gather Data", target_role="data_engineer")
    t2 = SubTaskAssignment(subtask_id="t2", title="Train Model", target_role="ml_engineer", dependencies=["t1"])
    t3 = SubTaskAssignment(subtask_id="t3", title="Evaluate Model", target_role="qa_specialist", dependencies=["t2"])

    planner.add_subtask(t1)
    planner.add_subtask(t2)
    planner.add_subtask(t3)

    # Initially, only t1 is ready
    ready = planner.get_executable_subtasks()
    assert len(ready) == 1
    assert ready[0].subtask_id == "t1"

    # Complete t1 -> t2 becomes ready
    planner.mark_completed("t1")
    ready = planner.get_executable_subtasks()
    assert len(ready) == 1
    assert ready[0].subtask_id == "t2"

    # Complete t2 -> t3 becomes ready
    planner.mark_completed("t2")
    ready = planner.get_executable_subtasks()
    assert len(ready) == 1
    assert ready[0].subtask_id == "t3"

    # Complete t3 -> all completed
    planner.mark_completed("t3")
    assert planner.is_all_completed() is True
    assert planner.has_failures() is False


def test_react_planner_step_parsing():
    planner = ReActPlanner(max_steps=5)

    # Step 1: Thought & Action with JSON input
    raw_step_1 = (
        "Thought: I need to query the user list.\n"
        "Action: fetch_users\n"
        'Action Input: {"limit": 10, "role": "admin"}'
    )
    step1 = planner.parse_step(raw_step_1)
    assert step1.thought == "I need to query the user list."
    assert step1.action == "fetch_users"
    assert isinstance(step1.action_input, dict)
    assert step1.action_input["limit"] == 10
    assert step1.is_final is False

    # Record observation
    planner.record_observation("Found 2 users: admin_1, admin_2")
    assert planner.steps[-1].observation == "Found 2 users: admin_1, admin_2"
    assert planner.is_finished() is False

    # Step 2: Final Answer
    raw_step_2 = (
        "Thought: I have the requested user list.\n"
        "Final Answer: There are 2 administrators: admin_1 and admin_2."
    )
    step2 = planner.parse_step(raw_step_2)
    assert step2.is_final is True
    assert step2.final_response == "There are 2 administrators: admin_1 and admin_2."
    assert planner.is_finished() is True
