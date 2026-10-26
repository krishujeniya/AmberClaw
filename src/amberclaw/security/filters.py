# ruff: noqa: RUF012, PLC0415, PLR0913
"""Tool Capability Manifest, Pre-Execution Input Filtering, and Post-Execution DLP.

Implements:
- ToolCapabilityManifest for explicit tool capability and risk declaration.
- Pre-execution argument validation, path traversal prevention, and secret leakage prevention.
- Post-execution output filtering, size bounds, PII redaction, and secret scrubbing.
"""

from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from amberclaw.security.approval import ToolRiskLevel
from amberclaw.security.audit import redact_secrets


class ArgumentValidationError(ValueError):
    """Raised when tool arguments fail strict schema or safety checks."""


class OutputPolicyViolationError(ValueError):
    """Raised when tool output violates DLP or safety policies."""


class ToolCapabilityManifest(BaseModel):
    """Declared capabilities, constraints, and risk classification of an agent tool."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str = ""
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    is_mutating: bool = False
    required_scopes: list[str] = Field(default_factory=list)
    idempotent: bool = True
    timeout_sec: int = 30
    schema_model: type[BaseModel] | None = None


class ToolExecutionFilter:
    """Enforces pre-execution input sanitization and post-execution output DLP."""

    DANGEROUS_TRAVERSAL_PATTERNS = ["../", "..\\", "%2e%2e", "\x00"]
    DANGEROUS_SHELL_INJECTION = [";", "&&", "||", "`", "$("]

    @classmethod
    def validate_arguments(
        cls,
        tool_name: str,
        args: dict[str, Any],
        manifest: ToolCapabilityManifest | None = None,
        strict_schema: bool = True,
        block_traversal: bool = True,
    ) -> dict[str, Any]:
        """Validate and sanitize arguments prior to tool execution."""
        # 1. Path traversal & null-byte inspection across string arguments
        if block_traversal:
            for k, v in args.items():
                if isinstance(v, str):
                    for pattern in cls.DANGEROUS_TRAVERSAL_PATTERNS:
                        if pattern in v:
                            logger.warning(
                                "Path traversal attempt blocked in tool '{}' param '{}'",
                                tool_name,
                                k,
                            )
                            raise ArgumentValidationError(
                                f"Path traversal pattern detected in parameter '{k}'"
                            )

        # 2. Strict Schema Validation against Pydantic schema model if declared
        if manifest and manifest.schema_model:
            try:
                # If strict_schema is requested, ensure no unmodeled extra fields exist
                if strict_schema:
                    valid_fields = set(manifest.schema_model.model_fields.keys())
                    extra_fields = set(args.keys()) - valid_fields
                    if extra_fields:
                        raise ArgumentValidationError(
                            f"Unexpected extra fields in arguments: {sorted(extra_fields)}"
                        )

                # Validate types through Pydantic
                validated = manifest.schema_model.model_validate(args)
                return validated.model_dump()
            except ValidationError as e:
                logger.error(
                    "Strict schema validation failed for tool '{}': {}", tool_name, e
                )
                raise ArgumentValidationError(f"Schema validation failed: {e}") from e

        return args

    @classmethod
    def filter_output(
        cls,
        tool_name: str,
        output: str,
        max_output_chars: int = 50000,
        redact_sensitive_secrets: bool = True,
        redact_pii: bool = False,
        enforce_dlp: bool = False,
        isolate_untrusted: bool = False,
    ) -> str:
        """Sanitize, redact, and bound tool output before returning it to LLM context."""
        if not isinstance(output, str):
            output = str(output)

        # 1. Truncate oversized output
        if len(output) > max_output_chars:
            logger.warning(
                "Tool '{}' output truncated from {} to {} chars",
                tool_name,
                len(output),
                max_output_chars,
            )
            output = (
                output[:max_output_chars]
                + f"\n\n[TRUNCATED: Output exceeded maximum limit of {max_output_chars} characters]"
            )

        # 2. DLP Inspection & Redaction
        if enforce_dlp:
            from amberclaw.security.dlp import DataLossPreventionEngine

            dlp_res = DataLossPreventionEngine.scan(output)
            output = dlp_res.clean_text

        # 3. Redact sensitive secrets (tokens, passwords, private keys)
        if redact_sensitive_secrets:
            output = redact_secrets(output)

        # 4. Optional PII redaction
        if redact_pii:
            from amberclaw.security.pii import PIIRedactor

            redactor = PIIRedactor()
            output = redactor.redact_text(output)

        # 5. Quarantine untrusted external tool outputs
        if isolate_untrusted:
            from amberclaw.security.prompt_guard import (
                TrustLevel,
                TrustProvenance,
                UntrustedContentFormatter,
            )

            provenance = TrustProvenance(
                source=f"tool:{tool_name}",
                origin=tool_name,
                trust_level=TrustLevel.UNTRUSTED_EXTERNAL,
            )
            output = UntrustedContentFormatter.wrap_untrusted(
                output, provenance=provenance
            )

        return output
