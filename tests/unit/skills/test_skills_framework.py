"""Unit tests for AmberClaw skills framework, scanner, registry, and hub client."""

from pathlib import Path

from amberclaw.skills.format import parse_skill_markdown, serialize_skill_markdown
from amberclaw.skills.hub import ClawHubClient, HubSkillPackage
from amberclaw.skills.loader import SkillLoader
from amberclaw.skills.registry import SkillRegistry
from amberclaw.skills.scanner import SkillScanner
from amberclaw.skills.skill import SkillDefinition, SkillMetadata
from amberclaw.skills.tracker import SkillUsageTracker


def test_format_parse_and_serialize():
    meta = SkillMetadata(
        name="pytest-expert",
        version="1.2.0",
        description="Generates robust pytest suites with high coverage",
        tags=["python", "testing", "pytest"],
    )
    instructions = "# Instructions\nAlways use fixtures and parametrize test cases."

    serialized = serialize_skill_markdown(meta, instructions)
    assert "name: pytest-expert" in serialized
    assert "version: 1.2.0" in serialized

    parsed_meta, parsed_body = parse_skill_markdown(serialized)
    assert parsed_meta.name == "pytest-expert"
    assert parsed_meta.version == "1.2.0"
    assert "Always use fixtures" in parsed_body


def test_skill_loader_and_scanner(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create skill 1
    s1_dir = skills_dir / "git-helper"
    s1_dir.mkdir()
    (s1_dir / "SKILL.md").write_text(
        "---\nname: git-helper\ndescription: Git workflow assistance\n---\nHelp with git.",
        encoding="utf-8",
    )

    # Create skill 2 with skill.json
    s2_dir = skills_dir / "docker-helper"
    s2_dir.mkdir()
    (s2_dir / "skill.json").write_text(
        '{"name": "docker-helper", "description": "Docker container helper"}',
        encoding="utf-8",
    )

    loader = SkillLoader()
    s1 = loader.load_from_directory(s1_dir)
    assert s1 is not None
    assert s1.name == "git-helper"

    scanner = SkillScanner(search_paths=[skills_dir])
    discovered = scanner.scan()
    names = [s.name for s in discovered]
    assert "git-helper" in names
    assert "docker-helper" in names


def test_skill_registry_and_search():
    registry = SkillRegistry()

    s1 = SkillDefinition(
        metadata=SkillMetadata(name="sql-pro", description="SQL queries and schema optimization", tags=["database", "sql"]),
        instructions="Optimize queries",
    )
    s2 = SkillDefinition(
        metadata=SkillMetadata(name="k8s-master", description="Kubernetes manifests", tags=["devops", "cloud"]),
        instructions="Build k8s configs",
    )

    registry.register(s1)
    registry.register(s2)

    expected_total = 2
    assert len(registry.list_all()) == expected_total
    assert registry.get("sql-pro") is not None

    # Search
    search_results = registry.search("database")
    assert len(search_results) == 1
    assert search_results[0].name == "sql-pro"

    # Toggle disabled
    registry.set_enabled("sql-pro", False)
    assert len(registry.list_all(enabled_only=True)) == 1
    assert len(registry.list_all(enabled_only=False)) == expected_total


def test_skill_usage_tracker():
    tracker = SkillUsageTracker()

    m = tracker.record_execution("sql-pro", duration_ms=150.0, success=True)
    assert m.invocations == 1
    assert m.successes == 1
    assert m.success_rate == 1.0

    m = tracker.record_execution("sql-pro", duration_ms=250.0, success=False)
    expected_invocations = 2
    expected_rate = 0.5
    expected_avg = 200.0
    assert m.invocations == expected_invocations
    assert m.failures == 1
    assert m.success_rate == expected_rate
    assert m.avg_execution_time_ms == expected_avg


def test_clawhub_client_install_and_package(tmp_path: Path):
    hub_client = ClawHubClient(local_skills_dir=tmp_path / "installed_skills")

    pkg = HubSkillPackage(
        name="cloud-architect",
        version="2.0.0",
        description="Design secure cloud architectures",
        tags=["aws", "gcp", "azure"],
        instructions="Follow well-architected framework principles.",
    )

    dest = hub_client.install_skill(pkg)
    assert dest.exists()
    assert (dest / "SKILL.md").exists()

    loader = SkillLoader()
    loaded = loader.load_from_directory(dest)
    assert loaded is not None
    assert loaded.name == "cloud-architect"

    packaged = hub_client.package_skill(loaded)
    assert packaged.name == "cloud-architect"
    assert packaged.version == "2.0.0"
