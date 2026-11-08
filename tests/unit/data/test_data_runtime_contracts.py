"""Offline graph routing and nullable persistence regressions."""

from importlib import import_module

import pytest
from langchain_core.language_models.fake import FakeListLLM
from sqlalchemy import create_engine

from amberclaw.data.templates import agent_templates
from amberclaw.data.utils.logging import log_ai_error, log_ai_function

REVIEW_FACTORIES = (
    ("data_cleaning", "recommend_cleaning_steps", "data_cleaner_function"),
    ("data_wrangling", "recommend_wrangling_steps", "data_wrangler_function"),
    ("data_visualization", "chart_instructor", "data_visualization_function"),
    (
        "feature_engineering",
        "recommend_feature_engineering_steps",
        "feature_engineer_function",
    ),
    ("sql_database", "recommend_sql_steps", "sql_database_function"),
)


@pytest.mark.parametrize("review_factory", REVIEW_FACTORIES)
@pytest.mark.parametrize(
    "bypass_flags", [(False, False), (False, True), (True, False), (True, True)]
)
@pytest.mark.parametrize("answer", ["yes", "please revise"])
def test_human_review_declares_and_uses_its_actual_destinations(
    monkeypatch, review_factory, bypass_flags, answer
):
    name, recommend, code_key = review_factory
    bypass_explain, bypass_recommended = bypass_flags
    module = import_module(f"amberclaw.data.agents.{name}_agent")
    factory = getattr(module, f"make_{name}_agent")
    kwargs = {
        "model": FakeListLLM(responses=["offline"]),
        "human_in_the_loop": True,
        "bypass_explain_code": bypass_explain,
        "bypass_recommended_steps": bypass_recommended,
    }
    engine = create_engine("sqlite://")
    if name == "sql_database":
        kwargs["connection"] = engine
    try:
        graph = factory(**kwargs)
        review_node = graph.builder.nodes["human_review"]
        success_destination = "__end__" if bypass_explain else "report_agent_outputs"
        assert set(review_node.ends) == {recommend, success_destination}
        monkeypatch.setattr(agent_templates, "interrupt", lambda **_: answer)
        command = review_node.runnable.invoke(
            {
                code_key: "def pipeline(): pass",
                "recommended_steps": "review",
                "user_instructions": None,
            }
        )
        expected = (
            ("__end__" if bypass_explain else "report_agent_outputs")
            if answer == "yes"
            else recommend
        )
        assert command.goto == expected
        if answer != "yes":
            assert "please revise" in command.update["user_instructions"]
    finally:
        engine.dispose()


def test_logging_uses_default_directory_for_explicit_none(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    path, name = log_ai_function("def pipeline(): pass", "pipeline.py", log_path=None)
    assert name == "pipeline.py"
    assert (tmp_path / path).read_text(encoding="utf-8") == "def pipeline(): pass"
    assert log_ai_error(None, log_path=None) is None
    assert not (tmp_path / "logs" / "errors.log").exists()
    error_path = log_ai_error("failure", log_path=None)
    assert (tmp_path / error_path).read_text(encoding="utf-8") == "failure\n"
    assert log_ai_function("ignored", "ignored.py", log=False, log_path=None) == (
        None,
        None,
    )
    assert log_ai_error(None, log=False, log_path=None) is None
