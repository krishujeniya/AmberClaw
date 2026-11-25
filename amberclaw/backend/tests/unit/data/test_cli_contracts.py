"""Exercise public data commands with an offline configured provider."""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from langchain_core.language_models.fake import FakeListLLM
from typer.testing import CliRunner

from amberclaw.config import loader
from amberclaw.data import cli
from amberclaw.providers import factory


@pytest.fixture
def configured_model(monkeypatch):
    config = MagicMock()
    config.agents.defaults.model = "configured/model"
    config.agents.defaults.temperature = 0.2
    config.agents.defaults.max_tokens = 321
    model = FakeListLLM(responses=["offline"])
    provider = MagicMock()
    provider.to_langchain_chat.return_value = model
    monkeypatch.setattr(loader, "load_config", lambda: config)
    make_provider = MagicMock(return_value=provider)
    monkeypatch.setattr(factory, "make_provider", make_provider)
    return model, config, provider, make_provider


def test_clean_command_passes_model_and_data_separately(
    monkeypatch, tmp_path, configured_model
):
    model, config, provider, make_provider = configured_model
    source = tmp_path / "raw.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    output = tmp_path / "cleaned.csv"
    agent = MagicMock()
    agent.get_data_cleaned.return_value = pd.DataFrame({"value": [2]})
    constructor = MagicMock(return_value=agent)
    monkeypatch.setattr(cli, "DataCleaningAgent", constructor)
    result = CliRunner().invoke(cli.app, ["clean", str(source), "-o", str(output)])
    assert result.exit_code == 0, result.output
    constructor.assert_called_once_with(model=model)
    assert agent.invoke_agent.call_args.kwargs["data_raw"].to_dict() == {
        "value": {0: 1}
    }
    make_provider.assert_called_once_with(config)
    provider.to_langchain_chat.assert_called_once_with(
        model="configured/model", temperature=0.2, max_tokens=321
    )
    assert pd.read_csv(output).to_dict() == {"value": {0: 2}}


@pytest.mark.usefixtures("configured_model")
def test_clean_command_reports_missing_result(monkeypatch, tmp_path):
    source = tmp_path / "raw.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    output = tmp_path / "missing.csv"
    agent = MagicMock()
    agent.get_data_cleaned.return_value = None
    monkeypatch.setattr(cli, "DataCleaningAgent", MagicMock(return_value=agent))
    result = CliRunner().invoke(cli.app, ["clean", str(source), "-o", str(output)])
    assert result.exit_code == 1
    assert "did not return cleaned data" in result.output
    assert not output.exists()


def test_viz_command_passes_loaded_data(monkeypatch, tmp_path, configured_model):
    source = tmp_path / "raw.csv"
    source.write_text("value\n3\n", encoding="utf-8")
    agent = MagicMock()
    constructor = MagicMock(return_value=agent)
    monkeypatch.setattr(cli, "DataVisualizationAgent", constructor)
    result = CliRunner().invoke(cli.app, ["viz", str(source), "--goal", "show values"])
    assert result.exit_code == 0, result.output
    constructor.assert_called_once_with(model=configured_model[0])
    assert agent.invoke_agent.call_args.kwargs["data_raw"].to_dict() == {
        "value": {0: 3}
    }
    assert agent.invoke_agent.call_args.kwargs["user_instructions"] == "show values"


def test_sql_command_reads_result_and_disposes_engine(
    monkeypatch, tmp_path, configured_model
):
    database = tmp_path / "database.sqlite"
    database.touch()
    engine = MagicMock()
    monkeypatch.setattr(
        cli, "create_engine", MagicMock(return_value=engine), raising=False
    )
    agent = MagicMock()
    agent.invoke_agent.return_value = None
    agent.get_data_sql.return_value = {"answer": {0: 42}}
    constructor = MagicMock(return_value=agent)
    monkeypatch.setattr(cli, "SQLDatabaseAgent", constructor)
    result = CliRunner().invoke(cli.app, ["sql", str(database), "count rows"])
    assert result.exit_code == 0, result.output
    constructor.assert_called_once_with(model=configured_model[0], connection=engine)
    assert "42" in result.output
    engine.dispose.assert_called_once()


def test_help_does_not_construct_provider(monkeypatch):
    load_config = MagicMock(
        side_effect=AssertionError("help must not load credentials")
    )
    monkeypatch.setattr(loader, "load_config", load_config)
    result = CliRunner().invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    load_config.assert_not_called()
