"""Network Policy Engine for AmberClaw.

Loads and evaluates YAML egress traffic rules for sandboxed agents.
"""

import re
from pathlib import Path
from typing import Any

import yaml

HTTPS_PORT = 443


class NetworkPolicy:
    """Manages egress network rules and checks target access permissions."""

    def __init__(
        self,
        allowed_hosts: list[str] | None = None,
        allowed_ports: list[int] | None = None,
        enforce_tls_only: bool = False,
        binary_rules: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.allowed_hosts = allowed_hosts or []
        self.allowed_ports = allowed_ports or [80, HTTPS_PORT]
        self.enforce_tls_only = enforce_tls_only
        self.binary_rules = binary_rules or {}

        self._compiled_patterns: list[re.Pattern] = []
        self._compile_patterns()

        self._compiled_binary_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_binary_patterns()

    def _compile_patterns(self) -> None:
        """Compile host glob patterns into regexes for speed."""
        self._compiled_patterns = []
        for host in self.allowed_hosts:
            if host.startswith("*."):
                base = host[2:]
                escaped_base = re.escape(base)
                pattern = re.compile(
                    r"^(.*\.)?" + escaped_base + r"$", re.IGNORECASE,
                )
            else:
                escaped = re.escape(host).replace(r"\*", ".*")
                pattern = re.compile(f"^{escaped}$", re.IGNORECASE)
            self._compiled_patterns.append(pattern)

    def _compile_binary_patterns(self) -> None:
        """Compile binary-specific host patterns."""
        self._compiled_binary_patterns = {}
        for binary, rules in self.binary_rules.items():
            hosts = rules.get("allowed_hosts", [])
            patterns = []
            for host in hosts:
                if host.startswith("*."):
                    base = host[2:]
                    escaped_base = re.escape(base)
                    pattern = re.compile(
                        r"^(.*\.)?" + escaped_base + r"$", re.IGNORECASE,
                    )
                else:
                    escaped = re.escape(host).replace(r"\*", ".*")
                    pattern = re.compile(f"^{escaped}$", re.IGNORECASE)
                patterns.append(pattern)
            self._compiled_binary_patterns[binary] = patterns

    @classmethod
    def load_from_yaml(cls, path: Path) -> "NetworkPolicy":
        """Load policy from YAML. Falls back to default if missing."""
        if not path.exists():
            return cls.default_policy()

        try:
            content = path.read_text(encoding="utf-8")
            data: dict[str, Any] = yaml.safe_load(content) or {}

            allowed_hosts = data.get("allowed_hosts", [])
            allowed_ports = data.get("allowed_ports", [80, HTTPS_PORT])
            enforce_tls_only = data.get("enforce_tls_only", False)
            binary_rules = data.get("binary_rules", {})

            return cls(
                allowed_hosts=allowed_hosts,
                allowed_ports=allowed_ports,
                enforce_tls_only=enforce_tls_only,
                binary_rules=binary_rules,
            )
        except Exception:
            return cls.default_policy()

    @classmethod
    def default_policy(cls) -> "NetworkPolicy":
        """Get the default minimal egress policy."""
        return cls(
            allowed_hosts=[
                "*.openai.com",
                "*.anthropic.com",
                "*.google.com",
                "*.googleapis.com",
                "api.tavily.com",
                "github.com",
                "api.github.com",
                "pypi.org",
                "files.pythonhosted.org",
            ],
            allowed_ports=[80, HTTPS_PORT],
            enforce_tls_only=False,
            binary_rules={
                "git": {
                    "allowed_hosts": ["github.com", "api.github.com"],
                    "allowed_ports": [HTTPS_PORT],
                },
                "pip": {
                    "allowed_hosts": ["pypi.org", "files.pythonhosted.org"],
                    "allowed_ports": [HTTPS_PORT],
                },
            },
        )

    def is_allowed(self, host: str, port: int, binary_context: str | None = None) -> bool:
        """Evaluate if the given host and port are allowed by the policy."""
        # 1. TLS-only check
        if self.enforce_tls_only and port != HTTPS_PORT:
            return False

        # 2. Binary-specific rules check
        if binary_context and binary_context in self.binary_rules:
            rules = self.binary_rules[binary_context]
            allowed_ports = rules.get("allowed_ports", [HTTPS_PORT])
            if port not in allowed_ports:
                return False

            allowed_hosts = rules.get("allowed_hosts", [])
            is_allowed_host = host.lower() in (h.lower() for h in allowed_hosts)
            return is_allowed_host or any(pattern.match(host) for pattern in self._compiled_binary_patterns.get(binary_context, []))

        # 3. Port check
        if port not in self.allowed_ports:
            return False

        # 4. Host check
        is_exact_allowed = host.lower() in (h.lower() for h in self.allowed_hosts)
        return is_exact_allowed or any(pattern.match(host) for pattern in self._compiled_patterns)
