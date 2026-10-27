"""JSON-backed persistent storage for Pydantic models.

Ensures agent profiles, tickets, and OS runtime state survive application restarts.
"""

import json
import threading
from pathlib import Path
from typing import Generic, TypeVar

from loguru import logger
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class JSONStateStore(Generic[T]):
    """Thread-safe persistent JSON store for Pydantic objects."""

    def __init__(self, file_path: str | Path, model_cls: type[T]):
        self.file_path = Path(file_path)
        self.model_cls = model_cls
        self._lock = threading.Lock()
        self._items: dict[str, T] = {}
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load items from disk into memory."""
        if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            self._items = {}
            return

        try:
            with self.file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                items = {}
                for key, val in data.items():
                    try:
                        items[key] = self.model_cls.model_validate(val)
                    except Exception as e:
                        logger.error(
                            "Failed to parse item {} from {}: {}",
                            key,
                            self.file_path,
                            e,
                        )
                self._items = items
        except Exception as e:
            logger.error(
                "Failed to load JSON state store from {}: {}", self.file_path, e
            )
            self._items = {}

    def _save(self) -> None:
        """Persist items to disk atomically."""
        tmp_path = self.file_path.with_suffix(".tmp")
        try:
            data = {}
            for key, item in self._items.items():
                if hasattr(item, "model_dump"):
                    data[key] = item.model_dump(mode="json")
                elif hasattr(item, "dict"):
                    data[key] = item.dict()
                else:
                    data[key] = item
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.file_path)
        except Exception as e:
            logger.error("Failed to save JSON state store to {}: {}", self.file_path, e)
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def get(self, key: str) -> T | None:
        """Get an item by key."""
        with self._lock:
            return self._items.get(key)

    def get_all(self) -> dict[str, T]:
        """Get a copy of all items."""
        with self._lock:
            return dict(self._items)

    def set(self, key: str, value: T) -> None:
        """Save/update an item by key."""
        with self._lock:
            self._items[key] = value
            self._save()

    def delete(self, key: str) -> bool:
        """Remove an item by key."""
        with self._lock:
            if key in self._items:
                del self._items[key]
                self._save()
                return True
            return False

    def contains(self, key: str) -> bool:
        """Check if key exists in store."""
        with self._lock:
            return key in self._items

    def count(self) -> int:
        """Get total item count."""
        with self._lock:
            return len(self._items)

    def clear(self) -> None:
        """Clear all items in the store and update disk state."""
        with self._lock:
            self._items.clear()
            self._save()
