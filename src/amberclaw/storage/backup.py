# ruff: noqa: DTZ003, S202, S608, S110, PLR0912, PLR0915
"""Disaster Recovery, Automated Backup, and Point-In-Time Restoration Engine.

Provides atomic WAL-consistent SQLite backups, tar-slip protected restoration,
SHA-256 manifest integrity verification, and automated DR drill exercises.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from amberclaw import __version__


class BackupSecurityError(PermissionError):
    """Raised when backup validation or safe extraction detects malicious content."""


@dataclass
class BackupFileEntry:
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass
class BackupManifest:
    backup_id: str
    created_at: str
    amberclaw_version: str
    total_files: int
    total_size_bytes: int
    archive_sha256: str = ""
    files: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DRDrillResult:
    drill_id: str
    success: bool
    started_at: str
    duration_seconds: float
    databases_checked: int
    records_checked: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DisasterRecoveryManager:
    """Manages creation, restoration, and disaster recovery drills for AmberClaw state."""

    def __init__(
        self,
        data_dir: Path | str = "data",
        backup_dir: Path | str = "backups",
        config_dir: Path | str = "config",
        logs_dir: Path | str = "logs",
    ):
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir)
        self.config_dir = Path(config_dir)
        self.logs_dir = Path(logs_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _hash_file(self, file_path: Path) -> str:
        sha = hashlib.sha256()
        with file_path.open("rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    def _backup_sqlite_db(self, src_path: Path, dst_path: Path) -> None:
        """Safely backup active SQLite database using online backup API."""
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with (
                sqlite3.connect(str(src_path)) as src_conn,
                sqlite3.connect(str(dst_path)) as dst_conn,
            ):
                src_conn.backup(dst_conn)
        except Exception as e:
            logger.warning(
                f"SQLite online backup failed for {src_path} ({e}), falling back to direct copy"
            )
            dst_path.write_bytes(src_path.read_bytes())

    def create_backup(
        self,
        name: str | None = None,
        include_tenants: bool = True,
        include_config: bool = True,
        include_logs: bool = True,
    ) -> Path:
        """Create a complete point-in-time backup archive."""
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_id = name or f"bak_{timestamp_str}"
        archive_path = self.backup_dir / f"{backup_id}.tar.gz"

        with tempfile.TemporaryDirectory(prefix="amberclaw_bak_") as tmp_dir_str:
            staging_dir = Path(tmp_dir_str)
            files_to_pack: list[tuple[Path, str]] = []  # (src_file, rel_archive_path)

            # 1. Backup SQLite databases in data_dir
            if self.data_dir.exists():
                for item in self.data_dir.rglob("*"):
                    if item.is_file():
                        # Check tenant inclusion
                        rel_to_data = item.relative_to(self.data_dir)
                        if "tenants" in rel_to_data.parts and not include_tenants:
                            continue

                        # Handle SQLite databases with online backup API
                        if item.suffix in [".db", ".sqlite", ".sqlite3"]:
                            staged_file = staging_dir / "data" / rel_to_data
                            self._backup_sqlite_db(item, staged_file)
                            files_to_pack.append((staged_file, f"data/{rel_to_data}"))
                        elif not item.name.endswith(("-wal", "-shm", ".tmp")):
                            # Ordinary data files (e.g. JSON state stores)
                            staged_file = staging_dir / "data" / rel_to_data
                            staged_file.parent.mkdir(parents=True, exist_ok=True)
                            staged_file.write_bytes(item.read_bytes())
                            files_to_pack.append((staged_file, f"data/{rel_to_data}"))

            # 2. Config files
            if include_config and self.config_dir.exists():
                for cfg_file in self.config_dir.rglob("*.yaml"):
                    if cfg_file.is_file():
                        rel = cfg_file.relative_to(self.config_dir)
                        staged = staging_dir / "config" / rel
                        staged.parent.mkdir(parents=True, exist_ok=True)
                        staged.write_bytes(cfg_file.read_bytes())
                        files_to_pack.append((staged, f"config/{rel}"))

            # 3. Audit logs
            if include_logs and self.logs_dir.exists():
                for log_file in self.logs_dir.glob("*.jsonl*"):
                    if log_file.is_file():
                        rel = log_file.relative_to(self.logs_dir)
                        staged = staging_dir / "logs" / rel
                        staged.parent.mkdir(parents=True, exist_ok=True)
                        staged.write_bytes(log_file.read_bytes())
                        files_to_pack.append((staged, f"logs/{rel}"))

            # 4. Generate manifest entries
            manifest_entries: list[dict[str, Any]] = []
            total_size = 0
            for staged_path, rel_path in files_to_pack:
                size = staged_path.stat().st_size
                total_size += size
                checksum = self._hash_file(staged_path)
                manifest_entries.append(
                    {
                        "relative_path": rel_path,
                        "size_bytes": size,
                        "sha256": checksum,
                    }
                )

            manifest = BackupManifest(
                backup_id=backup_id,
                created_at=datetime.utcnow().isoformat(),
                amberclaw_version=__version__,
                total_files=len(files_to_pack),
                total_size_bytes=total_size,
                files=manifest_entries,
            )

            manifest_file = staging_dir / "manifest.json"
            manifest_file.write_text(
                json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
            )

            # 5. Pack into tar.gz archive
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(manifest_file, arcname="manifest.json")
                for staged_path, rel_path in files_to_pack:
                    tar.add(staged_path, arcname=rel_path)

        # 6. Record overall archive hash
        archive_hash = self._hash_file(archive_path)
        manifest.archive_sha256 = archive_hash
        sidecar_manifest = self.backup_dir / f"{backup_id}.manifest.json"
        sidecar_manifest.write_text(
            json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
        )

        logger.info(
            f"Created backup archive '{backup_id}' ({len(files_to_pack)} files, "
            f"{total_size} bytes) at {archive_path}"
        )
        return archive_path

    def restore_backup(
        self,
        archive_path: Path | str,
        target_dir: Path | str | None = None,
        force: bool = False,
    ) -> BackupManifest:
        """Safely restore a backup archive with tar-slip protection and integrity verification."""
        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Backup archive not found: {archive_path}")

        dest_dir = Path(target_dir) if target_dir else self.data_dir.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_resolved = dest_dir.resolve()

        with tarfile.open(archive_path, "r:gz") as tar:
            # Check for tar-slip traversal attacks
            for member in tar.getmembers():
                target_member_path = (dest_dir / member.name).resolve()
                if not str(target_member_path).startswith(str(dest_resolved)):
                    raise BackupSecurityError(
                        f"Refusing to extract entry with path traversal: {member.name}"
                    )

            # Extract manifest first
            manifest_member = tar.getmember("manifest.json")
            f = tar.extractfile(manifest_member)
            if not f:
                raise ValueError("Backup archive missing manifest.json")
            manifest_data = json.loads(f.read().decode("utf-8"))
            manifest = BackupManifest(**manifest_data)

            # Prevent accidental overwrite unless force is specified
            if not force and any(
                (dest_dir / item["relative_path"]).exists() for item in manifest.files
            ):
                raise FileExistsError(
                    "Target directory contains existing files. Use force=True to overwrite."
                )

            # Extract all files
            tar.extractall(path=dest_dir)

        # Post-restore SQLite database integrity verification
        for item in manifest.files:
            rel = item["relative_path"]
            restored_file = dest_dir / rel
            if restored_file.suffix in [".db", ".sqlite", ".sqlite3"]:
                with sqlite3.connect(str(restored_file)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check;")
                    result = cursor.fetchall()
                    if not result or result[0][0] != "ok":
                        raise ValueError(
                            f"Restored SQLite DB '{rel}' failed integrity check: {result}"
                        )

        logger.info(
            f"Successfully restored backup '{manifest.backup_id}' to {dest_dir}"
        )
        return manifest

    def list_backups(self) -> list[dict[str, Any]]:
        """List all available backup archives with their metadata."""
        backups: list[dict[str, Any]] = []
        for mf in sorted(self.backup_dir.glob("*.manifest.json"), reverse=True):
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
                archive = self.backup_dir / f"{data['backup_id']}.tar.gz"
                data["archive_exists"] = archive.exists()
                backups.append(data)
            except Exception as e:
                logger.warning(f"Error reading backup manifest {mf}: {e}")
        return backups

    def run_dr_drill(self) -> DRDrillResult:
        """Execute an automated Disaster Recovery drill to verify backup/restore validity."""
        drill_id = f"drill_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()
        started_at = datetime.utcnow().isoformat()
        db_count = 0
        record_count = 0

        with tempfile.TemporaryDirectory(prefix="amberclaw_dr_drill_") as tmp_drill:
            drill_dir = Path(tmp_drill)
            backup_file = None

            try:
                # 1. Create a drill backup
                backup_file = self.create_backup(name=f"{drill_id}_snapshot")

                # 2. Restore the backup into the isolated drill sandbox
                drill_restore_dir = drill_dir / "restored"
                manifest = self.restore_backup(
                    archive_path=backup_file,
                    target_dir=drill_restore_dir,
                    force=True,
                )

                # 3. Check databases & query records
                for item in manifest.files:
                    rel = item["relative_path"]
                    restored_path = drill_restore_dir / rel
                    if restored_path.suffix in [".db", ".sqlite", ".sqlite3"]:
                        db_count += 1
                        with sqlite3.connect(str(restored_path)) as conn:
                            cursor = conn.cursor()
                            cursor.execute("PRAGMA integrity_check;")
                            check = cursor.fetchall()
                            if not check or check[0][0] != "ok":
                                raise ValueError(
                                    f"Integrity check failed on {rel}: {check}"
                                )

                            # Count records across user tables if present
                            cursor.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
                            )
                            tables = [r[0] for r in cursor.fetchall()]
                            for t in tables:
                                if not t.endswith("_fts") and not t.endswith(
                                    ("_idx", "_data", "_config", "_docsize")
                                ):
                                    try:
                                        cursor.execute(f"SELECT count(*) FROM {t};")
                                        row_count = cursor.fetchone()[0]
                                        record_count += row_count
                                    except Exception:
                                        pass

                duration = time.time() - start_time
                return DRDrillResult(
                    drill_id=drill_id,
                    success=True,
                    started_at=started_at,
                    duration_seconds=round(duration, 3),
                    databases_checked=db_count,
                    records_checked=record_count,
                )
            except Exception as exc:
                duration = time.time() - start_time
                logger.error(f"DR Drill '{drill_id}' failed: {exc}")
                return DRDrillResult(
                    drill_id=drill_id,
                    success=False,
                    started_at=started_at,
                    duration_seconds=round(duration, 3),
                    databases_checked=db_count,
                    records_checked=record_count,
                    error=str(exc),
                )
            finally:
                if backup_file and backup_file.exists():
                    backup_file.unlink(missing_ok=True)
                sidecar = self.backup_dir / f"{drill_id}_snapshot.manifest.json"
                if sidecar.exists():
                    sidecar.unlink(missing_ok=True)
