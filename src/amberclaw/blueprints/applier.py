"""Applies validated blueprint configurations to target runtime contexts."""

from typing import Any

from pydantic import BaseModel, Field

from amberclaw.blueprints.schema import BlueprintSchema
from amberclaw.blueprints.validator import BlueprintValidator


class BlueprintApplicationReport(BaseModel):
    """Execution report describing the changes applied by a blueprint."""

    blueprint_name: str
    success: bool
    applied_settings: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class BlueprintApplier:
    """Applies declarative blueprints to runtime configurations and environments."""

    def __init__(self, validator: BlueprintValidator | None = None) -> None:
        self.validator = validator or BlueprintValidator()

    def apply(
        self,
        blueprint: BlueprintSchema,
        target_config: dict[str, Any] | None = None,
    ) -> BlueprintApplicationReport:
        """Validate and merge blueprint parameters into target configuration dictionary."""
        val_res = self.validator.validate(blueprint)
        if not val_res.is_valid:
            return BlueprintApplicationReport(
                blueprint_name=blueprint.name,
                success=False,
                errors=val_res.errors,
            )

        applied: dict[str, Any] = (target_config or {}).copy()

        # Apply agent settings
        applied["agent"] = {
            "model_name": blueprint.agent.model_name,
            "temperature": blueprint.agent.temperature,
            "system_prompt": blueprint.agent.system_prompt,
            "max_turns": blueprint.agent.max_turns,
            "memory_nudge_enabled": blueprint.agent.memory_nudge_enabled,
        }

        # Apply security settings
        applied["security"] = {
            "sandbox_type": blueprint.security.sandbox_type,
            "allow_network_egress": blueprint.security.allow_network_egress,
            "restricted_paths": blueprint.security.restricted_paths,
            "require_human_approval_for_destructive": blueprint.security.require_human_approval_for_destructive,
        }

        # Apply skills and channels
        applied["skills"] = list(set(blueprint.skills))
        applied["channels"] = list(set(blueprint.channels))
        applied["blueprint_version"] = blueprint.version

        return BlueprintApplicationReport(
            blueprint_name=blueprint.name,
            success=True,
            applied_settings=applied,
        )
