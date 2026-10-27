"""Semantic validator for AmberClaw blueprint configurations."""

from pydantic import BaseModel, Field

from amberclaw.blueprints.schema import BlueprintSchema

VALID_SANDBOX_TYPES = {
    "daytona",
    "docker",
    "e2b",
    "local",
    "modal",
    "singularity",
    "ssh",
    "vercel",
    "wasm",
}

MIN_TEMPERATURE: float = 0.0
MAX_TEMPERATURE: float = 2.0


class BlueprintValidationResult(BaseModel):
    """Result of blueprint validation check."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BlueprintValidator:
    """Validates structural and semantic correctness of BlueprintSchema configurations."""

    def validate(self, blueprint: BlueprintSchema) -> BlueprintValidationResult:
        """Validate a blueprint configuration."""
        errors: list[str] = []
        warnings: list[str] = []

        # Validate name
        if not blueprint.name.strip():
            errors.append("Blueprint name cannot be empty.")

        # Validate sandbox type
        st = blueprint.security.sandbox_type.lower()
        if st not in VALID_SANDBOX_TYPES:
            errors.append(
                f"Invalid sandbox_type '{blueprint.security.sandbox_type}'. Must be one of {sorted(VALID_SANDBOX_TYPES)}."
            )

        # Validate temperature
        if not (MIN_TEMPERATURE <= blueprint.agent.temperature <= MAX_TEMPERATURE):
            errors.append(
                f"Temperature {blueprint.agent.temperature} must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}."
            )

        # Check duplicate skills
        if len(blueprint.skills) != len(set(blueprint.skills)):
            warnings.append("Duplicate skill names detected in blueprint skills list.")

        # Check duplicate channels
        if len(blueprint.channels) != len(set(blueprint.channels)):
            warnings.append("Duplicate channel names detected in blueprint channels list.")

        # Warnings for high security risk combinations
        if blueprint.security.sandbox_type == "local" and blueprint.security.allow_network_egress:
            warnings.append(
                "Local sandbox with unrestricted network egress enabled presents elevated security surface."
            )

        return BlueprintValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
