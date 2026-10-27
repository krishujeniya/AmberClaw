"""State schema migration runner and version transformer."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class MigrationStep(BaseModel):
    """A single version transition step."""

    from_version: int
    to_version: int
    description: str = ""
    transform_fn: Callable[[dict[str, Any]], dict[str, Any]] = Field(exclude=True)


class StateMigrator:
    """Manages versioned schema migration steps and transforms legacy state payloads."""

    def __init__(self) -> None:
        self._migrations: list[MigrationStep] = []

    def register_step(
        self,
        from_version: int,
        to_version: int,
        transform_fn: Callable[[dict[str, Any]], dict[str, Any]],
        description: str = "",
    ) -> None:
        """Register a migration transformation between schema versions."""
        step = MigrationStep(
            from_version=from_version,
            to_version=to_version,
            description=description,
            transform_fn=transform_fn,
        )
        self._migrations.append(step)

    def migrate(self, state: dict[str, Any], target_version: int) -> dict[str, Any]:
        """Apply sequential migrations from current schema version to target_version."""
        current = state.copy()
        current_version = int(current.get("schema_version", 1))

        if current_version == target_version:
            return current

        while current_version < target_version:
            # Find next valid step
            next_step = None
            for step in self._migrations:
                if step.from_version == current_version and step.to_version <= target_version:
                    next_step = step
                    break

            if not next_step:
                raise ValueError(
                    f"No migration path from version {current_version} to {target_version}."
                )

            current = next_step.transform_fn(current)
            current_version = next_step.to_version
            current["schema_version"] = current_version

        return current
