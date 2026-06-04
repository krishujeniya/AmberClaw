"""Unit tests for the SkillImprover and SkillManageTool."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amberclaw.agent.learning.skill_improver import SkillImprover
from amberclaw.agent.tools.skills import SkillManageArgs, SkillManageTool


@pytest.fixture
def fake_home(tmp_path: Path):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    return home_dir


@pytest.fixture
def skill_improver(tmp_path: Path, fake_home: Path):
    mock_provider = MagicMock()
    with patch("pathlib.Path.home", return_value=fake_home):
        return SkillImprover(mock_provider, tmp_path)


def test_telemetry_logging(skill_improver: SkillImprover):
    skill_improver.log_execution("test-skill", "success")
    skill_improver.log_execution("test-skill", "failure", "Something went wrong")

    expected_rate = 0.5
    assert skill_improver.get_success_rate("test-skill") == expected_rate
    assert skill_improver.get_success_rate("nonexistent") is None


@pytest.mark.asyncio
async def test_refinement_triggered(skill_improver: SkillImprover, fake_home: Path):
    # Log 3 failures and 1 success -> 25% success rate (< 50%)
    skill_improver.log_execution("test-skill", "failure", "Error A")
    skill_improver.log_execution("test-skill", "failure", "Error B")
    skill_improver.log_execution("test-skill", "failure", "Error C")
    skill_improver.log_execution("test-skill", "success")

    # Set up initial skill document in global auto-created dir
    skill_improver.global_skills_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_improver.global_skills_dir / "test-skill.md"
    skill_file.write_text(
        "---\n"
        "name: test-skill\n"
        "description: initial description\n"
        "---\n"
        "# Skill: Test Skill\n",
        encoding="utf-8"
    )

    # Set up initial skill in workspace as well
    workspace_dir = skill_improver.workspace_skills_dir / "test-skill"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    workspace_file = workspace_dir / "SKILL.md"
    workspace_file.write_text(skill_file.read_text(), encoding="utf-8")

    # Mock provider response for refinement
    mock_response = MagicMock()
    mock_response.content = (
        "---\n"
        "name: test-skill\n"
        "description: refined description\n"
        "---\n"
        "# Skill: Refined Test Skill\n"
    )
    skill_improver.provider.chat_with_retry = AsyncMock(return_value=mock_response)

    with patch("pathlib.Path.home", return_value=fake_home):
        refined = await skill_improver.check_and_refine("test-skill")

    assert refined is True
    assert "refined description" in skill_file.read_text(encoding="utf-8")
    assert "refined description" in workspace_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_skill_manage_tool(tmp_path: Path, fake_home: Path):
    tool = SkillManageTool(workspace=str(tmp_path))

    with patch("pathlib.Path.home", return_value=fake_home):
        # 1. Edit / Create
        content = "---\nname: skill-a\ndescription: skill a\n---\n# Skill A"
        res = await tool.run(SkillManageArgs(action="edit", skill_name="skill-a", content=content))
        assert "Successfully updated/created" in res
        assert (tool.global_skills_dir / "skill-a.md").exists()
        assert (tool.workspace_skills_dir / "skill-a" / "SKILL.md").exists()

        # 2. Merge
        content_b = "---\nname: skill-b\ndescription: skill b\n---\n# Skill B"
        await tool.run(SkillManageArgs(action="edit", skill_name="skill-b", content=content_b))

        res_merge = await tool.run(SkillManageArgs(
            action="merge",
            skill_name="skill-a",
            target_skill_name="skill-b"
        ))
        assert "Successfully merged" in res_merge
        assert (tool.global_skills_dir / "merged-skill-a-and-skill-b.md").exists()

        # Confirm originals were deleted
        assert not (tool.global_skills_dir / "skill-a.md").exists()
        assert not (tool.global_skills_dir / "skill-b.md").exists()

        # 3. Delete
        res_del = await tool.run(SkillManageArgs(action="delete", skill_name="merged-skill-a-and-skill-b"))
        assert "Successfully deleted" in res_del
        assert not (tool.global_skills_dir / "merged-skill-a-and-skill-b.md").exists()
