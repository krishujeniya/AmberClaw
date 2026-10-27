import pytest
from pathlib import Path
from amberclaw.templates import (
    TemplateManager,
    TemplateInstaller,
    TemplateScrubber,
    TemplateMarket,
    PersonaTemplate,
)


def test_template_manager_render():
    manager = TemplateManager()
    templates = manager.list_templates()
    assert "AGENTS.md" in templates
    assert "SOUL.md" in templates

    content = manager.read_template("AGENTS.md")
    assert len(content) > 0

    rendered = manager.render_template("AGENTS.md", {"user": "Alice"})
    assert isinstance(rendered, str)


def test_template_installer(tmp_path: Path):
    workspace = tmp_path / "new_workspace"
    installer = TemplateInstaller()

    installed = installer.install_workspace(workspace, context={"agent_name": "TestAgent"})
    assert len(installed) > 0
    assert (workspace / "AGENTS.md").exists()
    assert (workspace / "SOUL.md").exists()


def test_template_scrubber():
    dirty_context = {
        "user": "Bob",
        "api_key": "sk-123456789012345678901234567890123456789012345678",
    }
    scrubbed = TemplateScrubber.scrub_context(dirty_context)
    assert scrubbed["user"] == "Bob"
    assert "sk-123" in scrubbed["api_key"]
    assert "..." in scrubbed["api_key"]


def test_template_market():
    market = TemplateMarket()
    personas = market.list_personas()
    assert len(personas) >= 3

    default_p = market.get_persona("default-agent")
    assert default_p is not None
    assert default_p.name == "Default OS Assistant"

    new_p = PersonaTemplate(
        id="custom-bot",
        name="Custom Bot",
        description="Test custom persona",
    )
    market.register_persona(new_p)
    assert market.get_persona("custom-bot") is not None
