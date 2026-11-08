"""Unit and integration test suite for AmberClaw Data Science & Analytics Agents."""

from unittest.mock import MagicMock

import pytest

from amberclaw.data.agents.data_visualization_agent import DataVisualizationAgent
from amberclaw.data.agents.data_wrangling_agent import DataWranglingAgent
from amberclaw.data.agents.feature_engineering_agent import FeatureEngineeringAgent
from amberclaw.data.agents.sql_database_agent import SQLDatabaseAgent
from amberclaw.data.ds_agents.eda_tools_agent import EDAToolsAgent
from amberclaw.data.ml_agents.h2o_ml_agent import H2OMLAgent
from amberclaw.data.ml_agents.mlflow_tools_agent import MLflowToolsAgent


@pytest.fixture
def mock_model():
    return MagicMock()


@pytest.fixture
def mock_conn():
    return MagicMock()


def test_data_visualization_agent_initialization(mock_model):
    agent = DataVisualizationAgent(model=mock_model)
    assert agent is not None
    assert hasattr(agent, "get_workflow_summary")


def test_data_wrangling_agent_initialization(mock_model):
    agent = DataWranglingAgent(model=mock_model)
    assert agent is not None
    assert hasattr(agent, "get_workflow_summary")


def test_feature_engineering_agent_initialization(mock_model):
    agent = FeatureEngineeringAgent(model=mock_model)
    assert agent is not None
    assert hasattr(agent, "get_workflow_summary")


def test_sql_database_agent_initialization(mock_model, mock_conn):
    agent = SQLDatabaseAgent(model=mock_model, connection=mock_conn)
    assert agent is not None


def test_h2o_ml_agent_initialization(mock_model):
    agent = H2OMLAgent(model=mock_model)
    assert agent is not None
    assert hasattr(agent, "get_leaderboard")


def test_eda_tools_agent_initialization(mock_model):
    agent = EDAToolsAgent(model=mock_model)
    assert agent is not None
    assert hasattr(agent, "get_artifacts")


def test_mlflow_tools_agent_initialization(mock_model):
    try:
        agent = MLflowToolsAgent(model=mock_model)
        assert agent is not None
        assert hasattr(agent, "get_mlflow_artifacts")
    except ImportError as e:
        assert "MLflow is not installed" in str(e)
