"""Applies validated blueprint configurations to target runtime contexts."""

from typing import Any

from pydantic import BaseModel, Field

from amberclaw.blueprints.schema import BlueprintSchema
from amberclaw.blueprints.validator import BlueprintValidator
from amberclaw.config.schema import Config

# These channel flags are consumed by ChannelManager._init_channels.
_RUNTIME_CHANNELS = (
    "whatsapp",
    "telegram",
    "discord",
    "feishu",
    "mochat",
    "dingtalk",
    "email",
    "slack",
    "qq",
    "matrix",
)


def _unsupported_runtime_settings(blueprint: BlueprintSchema) -> list[str]:
    """Report requested fields without a canonical runtime consumer."""
    errors = []
    if (
        "security" in blueprint.model_fields_set
        and "sandbox_type" in blueprint.security.model_fields_set
    ):
        valid_sandboxes = {"docker", "local", "wasm", "modal"}
        if blueprint.security.sandbox_type not in valid_sandboxes:
            errors.append(
                f"security.sandbox_type: unsupported sandbox '{blueprint.security.sandbox_type}'. Allowed: {sorted(valid_sandboxes)}"
            )
    return errors


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
        """Build the legacy declarative dictionary, without enforcing runtime policy.

        Use apply_to_config for canonical runtime configuration and capability checks.
        """
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

    def apply_to_config(
        self, blueprint: BlueprintSchema, target_config: Config
    ) -> BlueprintApplicationReport:
        """Apply an explicit supported patch to the canonical runtime config.

        Omitted fields preserve existing configuration; schema defaults are not
        requests to change it. Name/version/description/metadata identify the
        blueprint and are not runtime settings. Explicit policy, skill, prompt,
        and memory requests fail before any partial result is returned.
        """
        errors = self.runtime_errors(blueprint)
        if errors:
            return BlueprintApplicationReport(
                blueprint_name=blueprint.name, success=False, errors=errors
            )

        applied = target_config.model_copy(deep=True)
        requested = blueprint.agent.model_fields_set
        if "model_name" in requested:
            applied.agents.defaults.model = blueprint.agent.model_name
        if "temperature" in requested:
            applied.agents.defaults.temperature = blueprint.agent.temperature
        if "max_turns" in requested:
            applied.agents.defaults.max_tool_iterations = blueprint.agent.max_turns
        if "system_prompt" in requested:
            applied.agents.defaults.system_prompt = blueprint.agent.system_prompt
        if "memory_nudge_enabled" in requested:
            applied.agents.defaults.memory_nudge_enabled = (
                blueprint.agent.memory_nudge_enabled
            )

        if "security" in blueprint.model_fields_set:
            sec_req = blueprint.security.model_fields_set
            if "sandbox_type" in sec_req:
                applied.security.sandbox_type = blueprint.security.sandbox_type
            if "allow_network_egress" in sec_req:
                applied.security.allow_network_egress = (
                    blueprint.security.allow_network_egress
                )
            if "restricted_paths" in sec_req:
                applied.security.restricted_paths = list(
                    blueprint.security.restricted_paths
                )
            if "require_human_approval_for_destructive" in sec_req:
                applied.security.require_human_approval_for_destructive = (
                    blueprint.security.require_human_approval_for_destructive
                )

        if "skills" in blueprint.model_fields_set:
            applied.skills = list(blueprint.skills)

        data = applied.model_dump()
        if "channels" in blueprint.model_fields_set:
            for name in _RUNTIME_CHANNELS:
                data["channels"][name]["enabled"] = name in blueprint.channels
        return BlueprintApplicationReport(
            blueprint_name=blueprint.name, success=True, applied_settings=data
        )

    def runtime_errors(self, blueprint: BlueprintSchema) -> list[str]:
        """Check runtime applicability before loading or migrating active config."""
        errors = list(self.validator.validate(blueprint).errors)
        errors.extend(_unsupported_runtime_settings(blueprint))
        unknown = sorted(set(blueprint.channels) - set(_RUNTIME_CHANNELS))
        errors.extend(f"channels: unsupported channel '{name}'." for name in unknown)
        return errors
