"""Explicitly selected skills must reach the agent's system context."""

from pathlib import Path

from amberclaw.agent.context import ContextBuilder


def test_selected_skill_content_is_loaded(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "focused" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: focused\ndescription: Focused test skill\n---\n"
        "Unique instructions for this selected task.\n",
        encoding="utf-8",
    )
    builder = ContextBuilder(tmp_path)
    assert (
        "Unique instructions for this selected task."
        not in builder.build_system_prompt()
    )
    assert "Unique instructions for this selected task." in builder.build_system_prompt(
        skill_names=["focused"]
    )
