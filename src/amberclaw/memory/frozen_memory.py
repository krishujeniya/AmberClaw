"""Frozen-snapshot memory system for AmberClaw.

Loads USER.md and MEMORY.md once at startup/instantiation and keeps
them cached in memory to preserve prefix caching behavior for LLM requests.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger


class FrozenSnapshotMemory:
    """Manages frozen-in-time snapshots of user profile and long-term memory."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.user_path = self.workspace / "USER.md"
        self.memory_path = self.workspace / "memory" / "MEMORY.md"

        self._user_content: str | None = None
        self._memory_content: str | None = None

        self._ensure_default_files()

    def _ensure_default_files(self) -> None:
        """Create template markdown files if they do not exist."""
        try:
            if not self.user_path.exists():
                self.user_path.write_text(
                    "# User Profile\n\n"
                    "- **Name**: User\n"
                    "- **Preferences**:\n"
                    "  - Style: Concise and direct\n",
                    encoding="utf-8",
                )
                logger.info(f"Created default user profile at {self.user_path}")

            memory_dir = self.memory_path.parent
            memory_dir.mkdir(parents=True, exist_ok=True)
            if not self.memory_path.exists():
                self.memory_path.write_text(
                    "# Long-Term Memory\n\n"
                    "- **Key Facts**:\n"
                    "  - No key facts recorded yet.\n",
                    encoding="utf-8",
                )
                logger.info(f"Created default memory file at {self.memory_path}")
        except Exception as e:
            logger.error(f"Failed to initialize default memory files: {e}")

    @property
    def user_profile(self) -> str:
        """Get the cached content of USER.md."""
        if self._user_content is None:
            try:
                if self.user_path.exists():
                    self._user_content = self.user_path.read_text(
                        encoding="utf-8",
                    ).strip()
                else:
                    self._user_content = ""
            except Exception as e:
                logger.error(f"Failed to read user profile: {e}")
                self._user_content = ""
        return self._user_content

    @property
    def memory_facts(self) -> str:
        """Get the cached content of MEMORY.md."""
        if self._memory_content is None:
            try:
                if self.memory_path.exists():
                    self._memory_content = self.memory_path.read_text(
                        encoding="utf-8",
                    ).strip()
                else:
                    self._memory_content = ""
            except Exception as e:
                logger.error(f"Failed to read long-term memory: {e}")
                self._memory_content = ""
        return self._memory_content

    def get_injection_block(self) -> str:
        """Return the formatted system prompt injection block."""
        parts = [
            "# User Profile & Memory Snapshot",
            "[Immutable snapshot loaded at session start]",
        ]

        profile = self.user_profile
        if profile:
            parts.extend(["## User Profile", profile])

        facts = self.memory_facts
        if facts:
            parts.extend(["## Long-Term Memory", facts])

        return "\n\n".join(parts)

    def reload(self) -> None:
        """Explicitly clear cache to trigger fresh read from disk on next request."""
        logger.info("Clearing frozen memory cache.")
        self._user_content = None
        self._memory_content = None
