# ruff: noqa: S603, S112, PLR0912, PLR2004
"""Secret scanning and redaction utility for AmberClaw."""

from __future__ import annotations

import math
import re
import subprocess
import tarfile
import zipfile
from collections import Counter
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


COMBINED_SECRET_PATTERN = re.compile(
    r"(?P<PRIVATE_KEY>-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----)|"
    r"(?P<OPENAI>\bsk-[a-zA-Z0-9]{48,}\b)|"
    r"(?P<ANTHROPIC>\bsk-ant-[a-zA-Z0-9]{30,}\b)|"
    r"(?P<GOOGLE>\bAIzaSy[a-zA-Z0-9_-]{33}\b)|"
    r"(?P<GITHUB>\bgh[oprs]_[a-zA-Z0-9]{36,}\b)|"
    r"(?P<SLACK>\bxox[baprs]-[a-zA-Z0-9-]{10,}\b)|"
    r"(?P<AWS>\bAKIA[0-9A-Z]{16}\b)"
)


class SecretScanner:
    """Scans text and files for credentials and redacts them to prevent leaks."""

    @staticmethod
    def calculate_entropy(text: str) -> float:
        """Calculate Shannon entropy (bits per symbol) for candidate text."""
        if not text:
            return 0.0
        counts = Counter(text)
        length = len(text)
        return -sum((c / length) * math.log2(c / length) for c in counts.values())

    @classmethod
    def scan_entropy(
        cls, text: str, min_length: int = 16, threshold: float = 3.8
    ) -> list[dict[str, Any]]:
        """Identify high-entropy candidate secrets (e.g. database credentials, signing keys)."""
        findings = []
        # Tokenize candidate strings by splitting on quotes, whitespace, and structural delimiters
        tokens = re.finditer(rf"[^\s\"\'\(\),;=\[\]{{}}<>]{{{min_length},}}", text)
        for m in tokens:
            token = m.group(0)
            # Skip common non-secrets: pure numbers, single case alphabetics
            if token.isdigit() or (
                token.isalpha() and (token.islower() or token.isupper())
            ):
                continue
            # Skip standard UUID format
            if re.match(
                r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
                token,
            ):
                continue
            entropy = cls.calculate_entropy(token)
            if entropy >= threshold:
                findings.append(
                    {
                        "type": "High-Entropy Secret",
                        "match": token,
                        "entropy": round(entropy, 2),
                        "start": m.start(),
                        "end": m.end(),
                    }
                )
        return findings

    @classmethod
    def scan_text(
        cls,
        text: str,
        check_entropy: bool = False,
        entropy_threshold: float = 3.8,
    ) -> list[dict[str, Any]]:
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
        if check_entropy:
            matched_spans = {(f["start"], f["end"]) for f in findings}
            for ef in cls.scan_entropy(text, threshold=entropy_threshold):
                if not any(
                    s <= ef["start"] and e >= ef["end"] for s, e in matched_spans
                ):
                    findings.append(ef)
        return findings

    @staticmethod
    def redact_text(text: str) -> str:
        """
        Scan a string and replace all detected secrets with redaction placeholders.
        Uses a high-performance single-pass combined regex.
        """
        # Fast exit if none of the candidate prefixes exist in text
        if not any(
            hint in text
            for hint in ("sk-", "AIzaSy", "gh", "xox", "AKIA", "-----BEGIN")
        ):
            return text

        def _replace_match(match: re.Match) -> str:
            if match.group("PRIVATE_KEY"):
                return "<PRIVATE KEY_REDACTED>"
            val = match.group(0)
            if len(val) <= 12:
                if match.group("OPENAI"):
                    name = "OPENAI API KEY"
                elif match.group("ANTHROPIC"):
                    name = "ANTHROPIC API KEY"
                elif match.group("GOOGLE"):
                    name = "GOOGLE API KEY"
                elif match.group("GITHUB"):
                    name = "GITHUB TOKEN"
                elif match.group("SLACK"):
                    name = "SLACK TOKEN"
                elif match.group("AWS"):
                    name = "AWS ACCESS KEY ID"
                else:
                    name = "SECRET"
                return f"<{name}_REDACTED>"
            return f"{val[:6]}...{val[-4:]}"

        return COMBINED_SECRET_PATTERN.sub(_replace_match, text)

    @classmethod
    def scan_file(
        cls, file_path: Path, check_entropy: bool = False
    ) -> list[dict[str, Any]]:
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
                        masked_val = (
                            f"{val[:6]}...{val[-4:]}" if len(val) > 10 else "..."
                        )
                        findings.append(
                            {
                                "file": str(file_path),
                                "line": line_idx,
                                "type": name,
                                "match_preview": masked_val,
                            }
                        )

        if check_entropy:
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, 1):
                for ef in cls.scan_entropy(line):
                    val = ef["match"]
                    masked_val = f"{val[:6]}...{val[-4:]}" if len(val) > 10 else "..."
                    findings.append(
                        {
                            "file": str(file_path),
                            "line": line_idx,
                            "type": "High-Entropy Secret",
                            "match_preview": masked_val,
                        }
                    )
        return findings

    @classmethod
    def scan_workspace(
        cls,
        workspace_dir: Path,
        exclude_patterns: set[str] | None = None,
        check_entropy: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Recursively scans the workspace directory for secrets, ignoring
        excluded directories/files.
        """
        excludes = (
            exclude_patterns
            if exclude_patterns is not None
            else DEFAULT_EXCLUDE_PATTERNS
        )
        findings = []

        if not workspace_dir.exists():
            return []

        for path in workspace_dir.rglob("*"):
            # Check if any path segment matches exclude patterns
            if any(part in excludes for part in path.parts):
                continue
            if path.is_file():
                findings.extend(cls.scan_file(path, check_entropy=check_entropy))

        return findings

    @classmethod
    def scan_git_history(
        cls, repo_dir: Path | str, max_commits: int = 50, check_entropy: bool = False
    ) -> list[dict[str, Any]]:
        """Scans git commit diff history for committed and subsequently deleted secrets."""
        repo_path = Path(repo_dir)
        if not (repo_path / ".git").exists():
            return []
        try:
            cmd = ["git", "log", "-p", f"-n{max_commits}", "--no-color"]
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                return []
        except Exception as e:
            logger.debug("Git history scan skipped: {}", e)
            return []

        findings: list[dict[str, Any]] = []
        current_commit = "HEAD"
        current_file = "unknown"

        for line in result.stdout.splitlines():
            if line.startswith("commit "):
                current_commit = line.split()[1][:10]
            elif line.startswith("+++ b/"):
                current_file = line[6:]
            elif line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                line_findings = cls.scan_text(content, check_entropy=check_entropy)
                for f in line_findings:
                    val = f["match"]
                    masked = f"{val[:6]}...{val[-4:]}" if len(val) > 10 else "..."
                    findings.append(
                        {
                            "source": "git_history",
                            "commit": current_commit,
                            "file": current_file,
                            "type": f["type"],
                            "match_preview": masked,
                        }
                    )
        return findings

    @classmethod
    def scan_archive(
        cls, archive_path: Path | str, check_entropy: bool = False
    ) -> list[dict[str, Any]]:
        """Scans archive packages (.tar, .tar.gz, .zip) in memory without disk extraction."""
        path = Path(archive_path)
        if not path.exists():
            return []
        findings: list[dict[str, Any]] = []

        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir() or info.file_size > 5 * 1024 * 1024:
                        continue
                    try:
                        content = zf.read(info).decode("utf-8", errors="ignore")
                        for line_idx, line in enumerate(content.splitlines(), 1):
                            for f in cls.scan_text(line, check_entropy=check_entropy):
                                val = f["match"]
                                masked = (
                                    f"{val[:6]}...{val[-4:]}"
                                    if len(val) > 10
                                    else "..."
                                )
                                findings.append(
                                    {
                                        "source": "archive",
                                        "archive": path.name,
                                        "member": info.filename,
                                        "line": line_idx,
                                        "type": f["type"],
                                        "match_preview": masked,
                                    }
                                )
                    except Exception:
                        continue
        elif tarfile.is_tarfile(path):
            with tarfile.open(path, "r:*") as tf:
                for member in tf.getmembers():
                    if not member.isfile() or member.size > 5 * 1024 * 1024:
                        continue
                    f_obj = tf.extractfile(member)
                    if not f_obj:
                        continue
                    try:
                        content = f_obj.read().decode("utf-8", errors="ignore")
                        for line_idx, line in enumerate(content.splitlines(), 1):
                            for f in cls.scan_text(line, check_entropy=check_entropy):
                                val = f["match"]
                                masked = (
                                    f"{val[:6]}...{val[-4:]}"
                                    if len(val) > 10
                                    else "..."
                                )
                                findings.append(
                                    {
                                        "source": "archive",
                                        "archive": path.name,
                                        "member": member.name,
                                        "line": line_idx,
                                        "type": f["type"],
                                        "match_preview": masked,
                                    }
                                )
                    except Exception:
                        continue
        return findings

    @classmethod
    def scan_json_payload(
        cls, payload: Any, path: str = "$", check_entropy: bool = False
    ) -> list[dict[str, Any]]:
        """Deeply inspect nested JSON objects, session turns, trajectories, or export archives."""
        findings: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            for k, v in payload.items():
                curr_path = f"{path}.{k}"
                findings.extend(
                    cls.scan_json_payload(v, curr_path, check_entropy=check_entropy)
                )
        elif isinstance(payload, list):
            for i, v in enumerate(payload):
                curr_path = f"{path}[{i}]"
                findings.extend(
                    cls.scan_json_payload(v, curr_path, check_entropy=check_entropy)
                )
        elif isinstance(payload, str):
            for f in cls.scan_text(payload, check_entropy=check_entropy):
                val = f["match"]
                masked = f"{val[:6]}...{val[-4:]}" if len(val) > 10 else "..."
                findings.append(
                    {
                        "source": "json_payload",
                        "path": path,
                        "type": f["type"],
                        "match_preview": masked,
                    }
                )
        return findings
