"""Offline regressions for skill root containment and legacy tool contracts."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from amberclaw.agent.tools import drive
from amberclaw.agent.tools.council import CouncilArgs as AgentCouncilArgs
from amberclaw.agent.tools.personal_rag import KnowledgeSearchTool
from amberclaw.agent.tools.skills import SkillManageArgs, SkillManageTool
from amberclaw.config.schema import GoogleDriveConfig
from amberclaw.providers.base import LLMProvider
from amberclaw.tools.reasoning import CouncilArgs, CouncilTool


@pytest.mark.asyncio
@pytest.mark.parametrize("skill_root", ["skills", "skills/auto-created"])
@pytest.mark.parametrize("action", ["edit", "delete"])
async def test_skill_manage_rejects_escaped_parent_root_before_mutation(
    tmp_path: Path, skill_root: str, action: str
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    original = outside / "example" / "SKILL.md"
    original.parent.mkdir(parents=True)
    original.write_text("original", encoding="utf-8")
    root = workspace / skill_root
    root.parent.mkdir(parents=True)
    root.symlink_to(outside, target_is_directory=True)
    tool = SkillManageTool(str(workspace))
    tool.global_skills_dir = tmp_path / "global"

    result = await tool.run(
        SkillManageArgs(action=action, skill_name="example", content="changed")
    )

    assert result.startswith("Error:")
    assert original.read_text(encoding="utf-8") == "original"
    assert not tool.global_skills_dir.exists()


@pytest.mark.asyncio
async def test_skill_manage_preserves_authorized_global_and_workspace_writes(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    tool = SkillManageTool(str(workspace))
    tool.global_skills_dir = tmp_path / "global"
    result = await tool.run(
        SkillManageArgs(action="edit", skill_name="example", content="content")
    )
    assert result.startswith("Successfully")
    assert (tool.global_skills_dir / "example.md").read_text() == "content"
    assert (workspace / "skills/auto-created/example/SKILL.md").read_text() == "content"


@pytest.mark.parametrize("values", [{}, {"models": None}])
def test_legacy_council_args_keep_nullable_models(values: dict[str, None]) -> None:
    args = CouncilArgs(query="question", **values)
    assert args.models is None


def test_legacy_council_schema_keeps_nullable_default() -> None:
    models = CouncilTool.args_schema.model_json_schema()["properties"]["models"]
    assert models["default"] is None
    assert {variant["type"] for variant in models["anyOf"]} == {"array", "null"}


@pytest.mark.asyncio
async def test_legacy_council_normalizes_nullable_models_for_canonical_runtime() -> (
    None
):
    provider = MagicMock(spec=LLMProvider)
    provider.get_default_model.return_value = "offline"
    tool = CouncilTool(provider)
    runtime = MagicMock()
    runtime.run = AsyncMock(return_value="answer")
    tool._council = runtime
    assert await tool.run("question", models=None) == "answer"
    runtime.run.assert_awaited_once_with(
        AgentCouncilArgs(query="question", models=[], depth=1)
    )


def test_drive_refresh_uses_request_and_persists_refreshed_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    credentials = MagicMock(valid=False, expired=True, refresh_token=object())
    credentials.to_json.return_value = '{"refreshed": true}'
    monkeypatch.setattr(
        drive.Credentials,
        "from_authorized_user_file",
        MagicMock(return_value=credentials),
    )
    request = object()
    monkeypatch.setattr(drive, "Request", MagicMock(return_value=request))
    service = object()
    build = MagicMock(return_value=service)
    monkeypatch.setattr(drive, "build", build)
    manager = drive.DriveManager(GoogleDriveConfig(token_json=str(token_path)))
    assert manager._get_service() is service
    credentials.refresh.assert_called_once_with(request)
    assert token_path.read_text(encoding="utf-8") == '{"refreshed": true}'
    build.assert_called_once_with("drive", "v3", credentials=credentials)


@pytest.mark.asyncio
async def test_rag_cosine_boundary_returns_float64_and_handles_zero_norm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = KnowledgeSearchTool(workspace=tmp_path)
    tool._save_vectors(np.array([[0.0, 0.0], [3.0, 4.0]], dtype=np.float64))
    monkeypatch.setattr(
        tool, "_get_embedding", AsyncMock(return_value=np.array([3.0, 4.0]))
    )
    with np.errstate(divide="raise", invalid="raise"):
        scores = await tool._semantic_scores(["zero", "matching"], "query")
    assert scores.dtype == np.dtype(np.float64)
    np.testing.assert_array_equal(scores, np.array([0.0, 1.0]))
