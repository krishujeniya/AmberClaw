"""Offline SQLite upgrade, backup, restore and rollback in a disposable directory."""

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

from amberclaw.database.migrator import (
    apply_migrations,
    get_current_revision,
    rollback_migrations,
)
from amberclaw.storage.backup import DisasterRecoveryManager


def run_drill() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="amberclaw-release-drill-") as temporary:
        root = Path(temporary)
        data = root / "data"
        data.mkdir()
        database = data / "amberclaw.db"
        url = f"sqlite:///{database}"
        if not apply_migrations(db_url=url):
            raise RuntimeError("SQLite upgrade failed")
        revision = get_current_revision(db_url=url)
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO agents (id, name, role, is_active) VALUES (?, ?, ?, ?)",
                ("offline-example", "Before upgrade", "assistant", 1),
            )
        manager = DisasterRecoveryManager(
            data_dir=data,
            backup_dir=root / "backups",
            config_dir=root / "config",
            logs_dir=root / "logs",
        )
        archive = manager.create_backup(
            name="before-upgrade", include_config=False, include_logs=False
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE agents SET name = ? WHERE id = ?",
                ("After upgrade", "offline-example"),
            )
        manager.restore_backup(archive, target_dir=root, force=True)
        with sqlite3.connect(database) as connection:
            restored = connection.execute(
                "SELECT name FROM agents WHERE id = ?", ("offline-example",)
            ).fetchone()
        if restored != ("Before upgrade",):
            raise RuntimeError("Backup restoration did not recover the original data")
        if (
            not rollback_migrations(db_url=url)
            or get_current_revision(db_url=url) is not None
        ):
            raise RuntimeError("SQLite schema rollback failed")
        if (
            not apply_migrations(db_url=url)
            or get_current_revision(db_url=url) != revision
        ):
            raise RuntimeError("SQLite re-upgrade failed")
        return {
            "scope": "Disposable local SQLite only; no target services or PostgreSQL",
            "upgrade_revision": revision,
            "data_restored": True,
            "schema_rollback": True,
            "reupgrade": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = json.dumps(run_drill(), indent=2)
    if args.out:
        args.out.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)  # noqa: T201 - this example reports its actual local results


if __name__ == "__main__":
    main()
