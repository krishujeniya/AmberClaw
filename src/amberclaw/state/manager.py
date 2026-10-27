"""Thread-safe persistent state manager and checkpoint engine."""

import json
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CheckpointMetadata(BaseModel):
    """Metadata describing a saved state checkpoint."""

    checkpoint_id: str
    created_at: float = Field(default_factory=time.time)
    description: str = ""
    state_keys: list[str] = Field(default_factory=list)


class StateManager:
    """Provides atomic key-value persistence, snapshot creation, and checkpoint restoration."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else None
        self._in_memory_state: dict[str, dict[str, Any]] = {}
        self._checkpoints: dict[str, dict[str, Any]] = {}
        self._checkpoint_meta: dict[str, CheckpointMetadata] = {}
        self._lock = threading.RLock()

        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self.storage_dir:
            return
        state_file = self.storage_dir / "state.json"
        if state_file.exists():
            try:
                self._in_memory_state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                self._in_memory_state = {}

    def _save_to_disk(self) -> None:
        if not self.storage_dir:
            return
        state_file = self.storage_dir / "state.json"
        tmp_file = self.storage_dir / "state.json.tmp"
        tmp_file.write_text(json.dumps(self._in_memory_state, indent=2), encoding="utf-8")
        tmp_file.replace(state_file)

    def save_state(self, key: str, data: dict[str, Any]) -> None:
        """Store or update state by key."""
        with self._lock:
            self._in_memory_state[key] = data.copy()
            self._save_to_disk()

    def get_state(self, key: str) -> dict[str, Any] | None:
        """Retrieve state by key."""
        with self._lock:
            val = self._in_memory_state.get(key)
            return val.copy() if val is not None else None

    def delete_state(self, key: str) -> bool:
        """Remove state entry by key."""
        with self._lock:
            if key in self._in_memory_state:
                del self._in_memory_state[key]
                self._save_to_disk()
                return True
            return False

    def list_keys(self) -> list[str]:
        """List all active state keys."""
        with self._lock:
            return list(self._in_memory_state.keys())

    def create_checkpoint(self, checkpoint_id: str, description: str = "") -> CheckpointMetadata:
        """Capture a snapshot of the current state repository."""
        with self._lock:
            snapshot = {k: v.copy() for k, v in self._in_memory_state.items()}
            self._checkpoints[checkpoint_id] = snapshot
            meta = CheckpointMetadata(
                checkpoint_id=checkpoint_id,
                description=description,
                state_keys=list(snapshot.keys()),
            )
            self._checkpoint_meta[checkpoint_id] = meta
            return meta

    def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """Restore in-memory state repository to a previously saved checkpoint snapshot."""
        with self._lock:
            snapshot = self._checkpoints.get(checkpoint_id)
            if snapshot is None:
                return False
            self._in_memory_state = {k: v.copy() for k, v in snapshot.items()}
            self._save_to_disk()
            return True

    def list_checkpoints(self) -> list[CheckpointMetadata]:
        """List all available checkpoints."""
        with self._lock:
            return list(self._checkpoint_meta.values())
