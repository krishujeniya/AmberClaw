# ruff: noqa: PLR0913
"""Multi-Tenant Isolation Engine for AmberClaw AI OS.

Provides schema-level (physical database partitioning) and query-level
access enforcement to prevent cross-tenant data leakage.
"""

from __future__ import annotations

import contextvars
from pathlib import Path
from typing import Any, Generic, TypeVar

from loguru import logger
from pydantic import BaseModel

from amberclaw.memory.session_db import SessionDB
from amberclaw.storage.persistence import JSONStateStore

T = TypeVar("T", bound=BaseModel)

_current_tenant_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_tenant_id", default=None
)


class CrossTenantAccessViolationError(PermissionError):
    """Raised when an operation attempts to access or manipulate data across tenant boundaries."""

    def __init__(self, requested_tenant: str | None, current_tenant: str | None):
        super().__init__(
            f"Cross-tenant access violation: Current tenant '{current_tenant}' cannot access "
            f"resources belonging to tenant '{requested_tenant}'."
        )
        self.requested_tenant = requested_tenant
        self.current_tenant = current_tenant


class TenantContext:
    """Task- and thread-safe context manager for tenant execution scoping."""

    def __init__(self, tenant_id: str):
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        self.tenant_id = tenant_id
        self._token: contextvars.Token | None = None

    def __enter__(self) -> TenantContext:
        self._token = _current_tenant_var.set(self.tenant_id)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token is not None:
            _current_tenant_var.reset(self._token)

    @classmethod
    def get_current(cls) -> str | None:
        """Retrieve active tenant ID from async execution context."""
        return _current_tenant_var.get()

    @classmethod
    def require_current(cls) -> str:
        """Retrieve active tenant ID or raise CrossTenantAccessViolationError if unassigned."""
        tenant = cls.get_current()
        if not tenant:
            raise CrossTenantAccessViolationError(
                requested_tenant="<any>", current_tenant=None
            )
        return tenant


class TenantIsolatedSessionDB:
    """Tenant-partitioned conversation session database.

    Guarantees physical file isolation (per-tenant SQLite files) and
    query-level predicate verification.
    """

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path("data/tenants")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._db_instances: dict[str, SessionDB] = {}

    def _resolve_tenant(self, explicit_tenant_id: str | None = None) -> str:
        current = TenantContext.get_current()
        if explicit_tenant_id and current and explicit_tenant_id != current:
            raise CrossTenantAccessViolationError(
                requested_tenant=explicit_tenant_id,
                current_tenant=current,
            )
        resolved = explicit_tenant_id or current
        if not resolved:
            raise CrossTenantAccessViolationError(
                requested_tenant=explicit_tenant_id,
                current_tenant=None,
            )
        return resolved

    def _get_tenant_db(self, tenant_id: str) -> SessionDB:
        if tenant_id not in self._db_instances:
            tenant_path = self.base_dir / tenant_id / "sessions.db"
            tenant_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_instances[tenant_id] = SessionDB(db_path=tenant_path)
        return self._db_instances[tenant_id]

    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        turn_index: int | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> int:
        """Store a conversation turn isolated within the tenant's partition."""
        active_tenant = self._resolve_tenant(tenant_id)
        db = self._get_tenant_db(active_tenant)
        return db.add_turn(
            session_id=session_id,
            role=role,
            content=content,
            turn_index=turn_index,
            metadata=metadata,
            user_id=user_id,
            agent_id=agent_id,
            org_id=active_tenant,
        )

    def get_turns(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve interaction turns strictly scoped to the tenant's partition."""
        active_tenant = self._resolve_tenant(tenant_id)
        db = self._get_tenant_db(active_tenant)
        return db.get_turns(
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            org_id=active_tenant,
        )

    def search_turns(
        self,
        query: str,
        session_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Perform FTS5 search scoped strictly to the tenant's partition."""
        active_tenant = self._resolve_tenant(tenant_id)
        db = self._get_tenant_db(active_tenant)
        return db.search_turns(
            query=query,
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            org_id=active_tenant,
        )

    def delete_session(self, session_id: str, tenant_id: str | None = None) -> int:
        """Delete all turns for a session within the tenant partition."""
        active_tenant = self._resolve_tenant(tenant_id)
        db = self._get_tenant_db(active_tenant)
        return db.delete_session(session_id)

    def purge_tenant_memory(self, tenant_id: str | None = None) -> int:
        """Purge all sessions exclusively for the given tenant."""
        active_tenant = self._resolve_tenant(tenant_id)
        db = self._get_tenant_db(active_tenant)
        return db.purge_all_sessions()

    def export_tenant_data(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """Export GDPR data portability archive scoped to tenant partition."""
        active_tenant = self._resolve_tenant(tenant_id)
        db = self._get_tenant_db(active_tenant)
        return db.export_user_data(
            user_id=user_id,
            session_id=session_id,
            org_id=active_tenant,
        )

    def close(self) -> None:
        """Close all tenant database handles."""
        for tid, db in self._db_instances.items():
            try:
                db.close()
            except Exception as e:
                logger.error(f"Error closing DB for tenant {tid}: {e}")
        self._db_instances.clear()


class TenantIsolatedStateStore(Generic[T]):
    """Thread-safe persistent JSON state store scoped per tenant partition."""

    def __init__(self, base_dir: Path | str, model_cls: type[T], file_name: str):
        self.base_dir = Path(base_dir)
        self.model_cls = model_cls
        self.file_name = file_name
        self._stores: dict[str, JSONStateStore[T]] = {}

    def _resolve_tenant(self, explicit_tenant_id: str | None = None) -> str:
        current = TenantContext.get_current()
        if explicit_tenant_id and current and explicit_tenant_id != current:
            raise CrossTenantAccessViolationError(
                requested_tenant=explicit_tenant_id,
                current_tenant=current,
            )
        resolved = explicit_tenant_id or current
        if not resolved:
            raise CrossTenantAccessViolationError(
                requested_tenant=explicit_tenant_id,
                current_tenant=None,
            )
        return resolved

    def _get_store(self, tenant_id: str) -> JSONStateStore[T]:
        if tenant_id not in self._stores:
            path = self.base_dir / tenant_id / self.file_name
            self._stores[tenant_id] = JSONStateStore(path, self.model_cls)
        return self._stores[tenant_id]

    def get(self, key: str, tenant_id: str | None = None) -> T | None:
        active = self._resolve_tenant(tenant_id)
        return self._get_store(active).get(key)

    def get_all(self, tenant_id: str | None = None) -> dict[str, T]:
        active = self._resolve_tenant(tenant_id)
        return self._get_store(active).get_all()

    def set(self, key: str, value: T, tenant_id: str | None = None) -> None:
        active = self._resolve_tenant(tenant_id)
        self._get_store(active).set(key, value)

    def delete(self, key: str, tenant_id: str | None = None) -> bool:
        active = self._resolve_tenant(tenant_id)
        return self._get_store(active).delete(key)
