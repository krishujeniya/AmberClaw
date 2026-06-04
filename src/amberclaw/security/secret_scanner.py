"""Secret scanning and redaction utility for AmberClaw."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

# High-fidelity regex patterns for common API keys and credentials
SECRET_PATTERNS = {
    "OpenAI API Key": re.compile(r"\bsk-[a-zA-Z0-9]{48,}\b"),
    "Anthropic API Key": re.compile(r"\bsk-ant-[a-zA-Z0-9]{30,}\b"),
    "Google API Key": re.compile(r"\bAIzaSy[a-zA-Z0-9_-]{33}\b"),
    "GitHub Token": re.compile(r"\bgh[oprs]_[a-zA-Z0-9]{36,}\b"),
    "Slack Token": re.compile(r"\bxox[baprs]-[a-zA-Z0-9-]{10,}\b"),
    "AWS Access Key ID": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Private Key": re.compile(
        r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----"
    ),
}

# Default directories and files to exclude from workspace scans
DEFAULT_EXCLUDE_PATTERNS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    "dist",
    "build",
    "vault.enc",
    ".vault_key",
}


class SecretScanner:
    """Scans text and files for credentials and redacts them to prevent leaks."""

    @staticmethod
    def scan_text(text: str) -> list[dict[str, Any]]:
        """
        Scan a string for secrets.

        Returns a list of dictionaries detailing the type of secret, the match,
        and its location.
        """
        findings = []
        for name, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(
                    {
                        "type": name,
                        "match": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        return findings

    @staticmethod
    def redact_text(text: str) -> str:
        """
        Scan a string and replace all detected secrets with redaction placeholders.
        """
        redacted = text
        for name, pattern in SECRET_PATTERNS.items():
            # For multiline private keys, replace the whole match
            if name == "Private Key":
                redacted = pattern.sub(f"<{name.upper()}_REDACTED>", redacted)
            else:
                # For inline keys, mask all but the prefix and suffix to retain context
                def mask_match(match: re.Match, name: str = name) -> str:
                    val = match.group(0)
                    if len(val) <= 12:  # noqa: PLR2004
                        return f"<{name.upper()}_REDACTED>"
                    return f"{val[:6]}...{val[-4:]}"

                redacted = pattern.sub(mask_match, redacted)
        return redacted

    @classmethod
    def scan_file(cls, file_path: Path) -> list[dict[str, Any]]:
        """Scan a single file for secrets and return any findings."""
        if not file_path.exists() or file_path.is_dir():
            return []

        # Skip binary files if possible
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.debug("Skipping non-text file {}: {}", file_path, e)
            return []

        findings = []
        for name, pattern in SECRET_PATTERNS.items():
            # For multiline search (like Private Keys)
            if name == "Private Key":
                for match in pattern.finditer(content):
                    # Calculate line number
                    line_num = content[: match.start()].count("\n") + 1
                    findings.append(
                        {
                            "file": str(file_path),
                            "line": line_num,
                            "type": name,
                            "match_preview": match.group(0)[:60] + "...",
                        }
                    )
            else:
                # Find line by line for precise reporting
                lines = content.splitlines()
                for line_idx, line in enumerate(lines, 1):
                    for match in pattern.finditer(line):
                        val = match.group(0)
                        masked_val = f"{val[:6]}...{val[-4:]}" if len(val) > 10 else "..."  # noqa: PLR2004
                        findings.append(
                            {
                                "file": str(file_path),
                                "line": line_idx,
                                "type": name,
                                "match_preview": masked_val,
                            }
                        )
        return findings

    @classmethod
    def scan_workspace(
        cls,
        workspace_dir: Path,
        exclude_patterns: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Recursively scans the workspace directory for secrets, ignoring
        excluded directories/files.
        """
        excludes = exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDE_PATTERNS
        findings = []

        if not workspace_dir.exists():
            return []

        for path in workspace_dir.rglob("*"):
            # Check if any path segment matches exclude patterns
            if any(part in excludes for part in path.parts):
                continue
            if path.is_file():
                findings.extend(cls.scan_file(path))

        return findings
