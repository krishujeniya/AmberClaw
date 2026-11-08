"""Offline regressions for tool dispatch and fail-closed input handling."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from amberclaw.agent.tools.council import CouncilArgs, CouncilTool
from amberclaw.agent.tools.gui import BrowserActionTool
from amberclaw.agent.tools.multimodal import AnalyzeVideoArgs, VideoAnalysisTool
from amberclaw.agent.tools.personal_rag import KnowledgeSearchArgs, KnowledgeSearchTool
from amberclaw.agent.tools.registry import ToolRegistry
from amberclaw.agent.tools.shell import ExecTool
from amberclaw.agent.tools.skills import (
    SkillInstallArgs,
    SkillInstallTool,
    SkillManageArgs,
    SkillManageTool,
)
from amberclaw.providers.base import LLMProvider, LLMResponse
from amberclaw.security.sandbox import CodeSandbox, ExecutionResult
from amberclaw.tools.batch_tools import PythonInterpreterTool
from amberclaw.tools.filesystem import ReadFileTool as SandboxedReadFileTool
from amberclaw.tools.reasoning import CouncilTool as LegacyCouncilTool
from amberclaw.tools.reasoning import MythosTool
from amberclaw.tools.subagent_tools import SpawnTool

EXPECTED_COUNCIL_CALLS = 7


def test_shell_guard_rejects_unresolvable_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        if str(path) == "/unresolvable":
            raise OSError("cannot resolve")
        return original(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)
    error = ExecTool()._guard_command("cat /unresolvable", str(tmp_path))
    assert error is not None and "blocked" in error


@pytest.mark.asyncio
async def test_gui_uses_registry_keyword_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = BrowserActionTool()
    monkeypatch.setattr(tool, "_execute_playwright", AsyncMock(return_value="page"))
    registry = ToolRegistry()
    registry.register(tool)
    assert await registry.execute("browser_action", {"action": "get_content"}) == "page"


@pytest.mark.asyncio
@pytest.mark.parametrize("slug", ["../escape", "/outside/escape", "--workdir", "a/b"])
async def test_skill_install_rejects_path_and_option_slugs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, slug: str
) -> None:
    launch = AsyncMock()
    launch.return_value.communicate.return_value = (b"ok", b"")
    launch.return_value.returncode = 0
    monkeypatch.setattr("asyncio.create_subprocess_exec", launch)
    result = await SkillInstallTool(str(tmp_path)).run(SkillInstallArgs(slug=slug))
    assert result.startswith("Error:")
    launch.assert_not_called()


@pytest.mark.asyncio
async def test_rag_empty_and_keyword_result_order(tmp_path: Path) -> None:
    tool = KnowledgeSearchTool(workspace=tmp_path)
    assert (
        await tool.run(KnowledgeSearchArgs(query="python"))
        == "Knowledge base is empty."
    )
    tool._save_kb(
        {
            "entries": [
                {"content": "python asyncio task", "tags": ["code"]},
                {"content": "oranges orchard fruit", "tags": []},
            ]
        }
    )
    assert await tool.run(KnowledgeSearchArgs(query="python", limit=1)) == (
        "Result 1:\npython asyncio task [tags: code]"
    )


@pytest.mark.asyncio
async def test_video_capture_is_released_when_metadata_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    video = tmp_path / "empty.mp4"
    video.touch()
    cv2 = MagicMock()
    capture = cv2.VideoCapture.return_value
    capture.get.return_value = 0
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    provider = MagicMock()
    assert await VideoAnalysisTool(provider).run(AnalyzeVideoArgs(path=str(video))) == (
        "Error: Could not read video frames."
    )
    capture.release.assert_called_once()


@pytest.mark.asyncio
async def test_rag_zero_vectors_are_finite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    tool = KnowledgeSearchTool(workspace=tmp_path)
    tool._save_vectors(np.array([[0.0, 0.0], [1.0, 0.0]]))
    monkeypatch.setattr(
        tool, "_get_embedding", AsyncMock(return_value=np.array([1.0, 0.0]))
    )
    with np.errstate(divide="raise", invalid="raise"):
        assert (await tool._semantic_scores(["a", "b"], "q")).tolist() == [0.0, 1.0]


@pytest.mark.asyncio
async def test_council_depth_keeps_and_reconsiders_all_rankings() -> None:

    provider = MagicMock(spec=LLMProvider)
    provider.chat_with_retry = AsyncMock(
        side_effect=[
            LLMResponse(content="first answer"),
            LLMResponse(content="second answer"),
            LLMResponse(content="first review A"),
            LLMResponse(content="first review B"),
            LLMResponse(content="second review A"),
            LLMResponse(content="second review B"),
            LLMResponse(content="conclusion"),
        ]
    )
    result = await CouncilTool(provider, "one").run(
        CouncilArgs(query="question", models=["one", "two"], depth=2)
    )
    calls = provider.chat_with_retry.call_args_list
    assert len(calls) == EXPECTED_COUNCIL_CALLS
    assert "first review A" in calls[4].kwargs["messages"][0]["content"]
    synthesis = calls[6].kwargs["messages"][0]["content"]
    assert "first review A" in synthesis and "second review A" in synthesis
    assert "conclusion" in result


@pytest.mark.asyncio
async def test_optional_tool_runtimes_fail_safely_without_injection() -> None:

    assert (await PythonInterpreterTool().run("print('hello')")).startswith("Error:")
    assert (await LegacyCouncilTool().run("question")).startswith("Error:")
    assert (await MythosTool().run("question")).startswith("Error:")
    assert (await SpawnTool().run("task")).startswith("Error:")


@pytest.mark.asyncio
async def test_skill_manage_rejects_traversal_before_writes(tmp_path: Path) -> None:

    tool = SkillManageTool(str(tmp_path / "workspace"))
    tool.global_skills_dir = tmp_path / "global"
    result = await tool.run(
        SkillManageArgs(action="edit", skill_name="../escaped", content="x")
    )
    assert result.startswith("Error:")
    assert not (tmp_path / "escaped.md").exists()


@pytest.mark.asyncio
async def test_skill_manage_rejects_symlink_before_writes(tmp_path: Path) -> None:

    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "skills").mkdir(parents=True)
    (workspace / "skills" / "linked").symlink_to(outside, target_is_directory=True)
    tool = SkillManageTool(str(workspace))
    tool.global_skills_dir = tmp_path / "global"
    result = await tool.run(SkillManageArgs(action="delete", skill_name="linked"))
    assert result.startswith("Error:")
    assert outside.is_dir()


@pytest.mark.asyncio
async def test_skill_install_rejects_existing_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = tmp_path / "workspace"
    (workspace / "skills").mkdir(parents=True)
    (workspace / "skills" / "linked").symlink_to(outside, target_is_directory=True)
    launch = AsyncMock()
    launch.return_value.communicate.return_value = (b"ok", b"")
    launch.return_value.returncode = 0
    monkeypatch.setattr("asyncio.create_subprocess_exec", launch)
    result = await SkillInstallTool(str(workspace)).run(SkillInstallArgs(slug="linked"))
    assert result.startswith("Error:")
    launch.assert_not_called()


@pytest.mark.asyncio
async def test_injected_legacy_reasoning_and_code_use_current_runtime() -> None:

    provider = MagicMock(spec=LLMProvider)
    provider.get_default_model.return_value = "one"
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="answer"))
    result = await LegacyCouncilTool(provider).run("question", depth=2)
    assert "answer" in result
    assert provider.chat_with_retry.await_count == EXPECTED_COUNCIL_CALLS
    sandbox = MagicMock(spec=CodeSandbox)
    sandbox.execute_python = AsyncMock(
        return_value=ExecutionResult(
            stdout="result",
            stderr="",
            exit_code=0,
            execution_time_ms=1.0,
        )
    )
    assert await PythonInterpreterTool(sandbox).run("print('hello')") == "result"
    sandbox.execute_python.assert_awaited_once_with("print('hello')")


@pytest.mark.asyncio
async def test_filesystem_adapter_requires_and_uses_injected_sandbox() -> None:
    assert (await SandboxedReadFileTool().run("file.txt")).startswith("Error:")
    sandbox = MagicMock()
    sandbox.read_file = AsyncMock(
        return_value=SimpleNamespace(success=True, output="content", error=None)
    )
    tool = SandboxedReadFileTool(sandbox=sandbox)
    assert tool.sandbox is sandbox
    assert await tool.run("file.txt") == "content"
    sandbox.read_file.assert_awaited_once_with("file.txt")
