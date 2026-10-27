"""Parser and serializer for SKILL.md Markdown frontmatter format."""

import re
from typing import Any

import yaml

from amberclaw.skills.skill import SkillMetadata


def parse_skill_markdown(content: str) -> tuple[SkillMetadata, str]:
    """Parse a SKILL.md file with YAML frontmatter into SkillMetadata and instructions body."""
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)

    if not frontmatter_match:
        # No frontmatter, treat entire file as instructions
        meta = SkillMetadata(name="unnamed_skill", description="Skill without frontmatter")
        return meta, content.strip()

    frontmatter_yaml = frontmatter_match.group(1)
    body = frontmatter_match.group(2).strip()

    try:
        parsed_yaml: dict[str, Any] = yaml.safe_load(frontmatter_yaml) or {}
    except Exception:
        parsed_yaml = {}

    name = parsed_yaml.get("name", "unnamed_skill")
    version = str(parsed_yaml.get("version", "1.0.0"))
    description = parsed_yaml.get("description", "")
    author = parsed_yaml.get("author")
    tags = parsed_yaml.get("tags", [])
    dependencies = parsed_yaml.get("dependencies", [])
    entrypoint = parsed_yaml.get("entrypoint")
    is_enabled = bool(parsed_yaml.get("is_enabled", True))

    meta = SkillMetadata(
        name=name,
        version=version,
        description=description,
        author=author,
        tags=tags if isinstance(tags, list) else [str(tags)],
        dependencies=dependencies if isinstance(dependencies, list) else [],
        entrypoint=entrypoint,
        is_enabled=is_enabled,
    )

    return meta, body


def serialize_skill_markdown(metadata: SkillMetadata, instructions: str) -> str:
    """Serialize SkillMetadata and instructions into SKILL.md string with frontmatter."""
    data = {
        "name": metadata.name,
        "version": metadata.version,
        "description": metadata.description,
        "tags": metadata.tags,
        "dependencies": metadata.dependencies,
        "is_enabled": metadata.is_enabled,
    }
    if metadata.author:
        data["author"] = metadata.author
    if metadata.entrypoint:
        data["entrypoint"] = metadata.entrypoint

    yaml_header = yaml.dump(data, sort_keys=False, default_flow_style=False).strip()
    return f"---\n{yaml_header}\n---\n\n{instructions.strip()}\n"
