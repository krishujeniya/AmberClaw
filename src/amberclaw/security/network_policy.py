"""Network Policy Engine for AmberClaw.

Loads and evaluates YAML egress traffic rules for sandboxed agents.
"""

import re
from pathlib import Path
from typing import Any

import yaml


class NetworkPolicy:
    """Manages egress network rules and checks target access permissions."""

    def __init__(
        self,
        allowed_hosts: list[str] | None = None,
        allowed_ports: list[int] | None = None,
    ) -> None:
        self.allowed_hosts = allowed_hosts or []
        self.allowed_ports = allowed_ports or [80, 443]
        self._compiled_patterns: list[re.Pattern] = []
        self._compile_patterns()

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

    @classmethod
    def load_from_yaml(cls, path: Path) -> "NetworkPolicy":
        """Load policy from YAML. Falls back to default if missing."""
        if not path.exists():
            return cls.default_policy()

        try:
            content = path.read_text(encoding="utf-8")
            data: dict[str, Any] = yaml.safe_load(content) or {}

            allowed_hosts = data.get("allowed_hosts", [])
            allowed_ports = data.get("allowed_ports", [80, 443])

            return cls(allowed_hosts=allowed_hosts, allowed_ports=allowed_ports)
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
            allowed_ports=[80, 443],
        )

    def is_allowed(self, host: str, port: int) -> bool:
        """Evaluate if the given host and port are allowed by the policy."""
        # 1. Port check
        if port not in self.allowed_ports:
            return False

        # 2. Host check
        # Check against direct exact hosts first
        if host.lower() in (h.lower() for h in self.allowed_hosts):
            return True

        # Check against wildcard patterns
        return any(pattern.match(host) for pattern in self._compiled_patterns)
