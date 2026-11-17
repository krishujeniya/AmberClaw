# ruff: noqa: S101
"""Typed Tool and Protocol Contracts with Schema Versioning (CL-020).

Ensures:
- Strict versioned input and output schema enforcement.
- Predictable failures on malformed tool outputs.
- Preservation and verification of authorization scopes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class ExecutionScope(StrEnum):
    READ_ONLY = "read_only"
    IDEMPOTENT_WRITE = "idempotent_write"
    IRREVERSIBLE_SIDE_EFFECT = "irreversible_side_effect"


class ToolContractError(RuntimeError):
    """Base error for tool contract violations."""


class InsufficientScopeError(ToolContractError):
    """Raised when caller lacks required authorization scopes."""


class MalformedToolInputError(ToolContractError):
    """Raised when tool arguments fail schema validation."""


class MalformedToolOutputError(ToolContractError):
    """Raised when tool output fails return contract schema validation."""


class ToolContract(BaseModel):
    """Typed, versioned contract defining tool parameters, outputs, and security scopes."""

    tool_name: str
    schema_version: str = "1.0.0"
    description: str
    execution_scope: ExecutionScope = ExecutionScope.READ_ONLY
    required_scopes: list[str] = Field(default_factory=list)
    input_model: type[BaseModel] | None = None
    output_model: type[BaseModel] | None = None

    def validate_caller_scopes(self, caller_scopes: set[str] | list[str]) -> None:
        """Verify that caller has all required authorization scopes."""
        provided = set(caller_scopes)
        missing = [s for s in self.required_scopes if s not in provided]
        if missing:
            raise InsufficientScopeError(
                f"Caller lacks required scopes for tool '{self.tool_name}': {missing}"
            )

    def validate_inputs(self, raw_inputs: dict[str, Any]) -> BaseModel | dict[str, Any]:
        """Validate input arguments against input contract model."""
        if self.input_model is None:
            return raw_inputs
        try:
            return self.input_model.model_validate(raw_inputs)
        except ValidationError as exc:
            raise MalformedToolInputError(
                f"Tool '{self.tool_name}' received malformed inputs: {exc.errors()}"
            ) from exc

    def validate_output(self, raw_output: Any) -> Any:
        """Validate returned tool output against output contract model."""
        if self.output_model is None:
            return raw_output
        try:
            if isinstance(raw_output, str):
                try:
                    parsed = json.loads(raw_output)
                    if isinstance(parsed, dict):
                        return self.output_model.model_validate(parsed)
                except json.JSONDecodeError:
                    pass
            elif isinstance(raw_output, dict):
                return self.output_model.model_validate(raw_output)

            # If raw_output is already an instance of output_model
            if isinstance(raw_output, self.output_model):
                return raw_output

            raise MalformedToolOutputError(
                f"Tool '{self.tool_name}' produced output incompatible with model "
                f"{self.output_model.__name__}: type={type(raw_output).__name__}"
            )
        except ValidationError as exc:
            raise MalformedToolOutputError(
                f"Tool '{self.tool_name}' output failed contract schema validation: {exc.errors()}"
            ) from exc
