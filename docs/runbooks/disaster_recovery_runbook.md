# SQLite and file recovery runbook

`DisasterRecoveryManager` backs up local SQLite databases and selected files into
a tar.gz archive with a SHA-256 manifest. It uses SQLite's online backup API.
This is a snapshot facility; remote PostgreSQL backup, incremental point-in-time
recovery, archive encryption and an `amberclaw backup` CLI are not implemented by
this manager. Use the actual library API below.

## Verify the procedure locally

From the repository root:

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True uv run python examples/release_drill.py
```

The example creates a disposable SQLite database, upgrades its schema, inserts a
record, creates a backup, changes the record, restores the original data, rolls
the schema back and re-applies it. It prints the actual checks and cleans up the
temporary directory. It does not stop services or touch production data.

## Create and inspect a real snapshot

Supply the deployment's actual data/config/log paths; defaults below describe a
checkout layout and must be checked against the running application:

```python
from pathlib import Path
from amberclaw.storage.backup import DisasterRecoveryManager

manager = DisasterRecoveryManager(
    data_dir=Path("data"), backup_dir=Path("backups"),
    config_dir=Path("config"), logs_dir=Path("logs"),
)
archive = manager.create_backup()
print(archive)
print(manager.list_backups())
```

Keep snapshots and their sidecar manifests in trusted, access-controlled storage.
Hashes detect mismatches; they do not authenticate an attacker-replaced archive
and manifest. Protect backups containing configuration or client data according
to the deployment's storage policy.

## Restore into a separate directory

Stop every application writer using the deployment's real service manager before
replacing live state. Keep the original data and executable environment available
for rollback. First restore into a fresh, separate directory:

```python
from pathlib import Path
restored = manager.restore_backup(
    archive_path=archive,
    target_dir=Path("restore-review"),
)
print(restored.backup_id)
```

Restoration rejects traversal paths, archive links, devices, duplicate/unlisted
files and mismatched manifest sizes/hashes. SQLite integrity checks run in staging
before destination writes. Existing files require explicit `force=True`; that
option does not bypass security or integrity validation. Review recovered files
and application-level records before choosing any live destination.

Start the matching application revision only after its data, authentication,
provider and channel checks pass. Record the target commands and outcomes.
The disposable local drill does not establish target restoration or deployment
rollback acceptance. See [the upgrade guide](../upgrade-stabilization.md).
