"""AmberClaw declarative blueprints schema, loader, validator, and applier."""

from pydantic import BaseModel, Field

from amberclaw.blueprints.applier import (
    BlueprintApplicationReport,
    BlueprintApplier,
)
from amberclaw.blueprints.loader import BlueprintLoader
from amberclaw.blueprints.schema import (
    AgentBlueprintConfig,
    BlueprintSchema,
    SecurityBlueprintConfig,
)
from amberclaw.blueprints.validator import (
    VALID_SANDBOX_TYPES,
    BlueprintValidationResult,
    BlueprintValidator,
)


class BlueprintsModuleConfig(BaseModel):
    """Configuration for the amberclaw.blueprints module."""

    enabled: bool = Field(default=True, description="Whether the module is enabled")
    version: str = Field(default="2026.0.1", description="Module version")


__all__ = [
    "VALID_SANDBOX_TYPES",
    "AgentBlueprintConfig",
    "BlueprintApplicationReport",
    "BlueprintApplier",
    "BlueprintLoader",
    "BlueprintSchema",
    "BlueprintValidationResult",
    "BlueprintValidator",
    "BlueprintsModuleConfig",
    "SecurityBlueprintConfig",
]
