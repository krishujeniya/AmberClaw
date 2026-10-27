# Incident Runbook: Disaster Recovery & Database Restoration

## Overview
This runbook details procedure for restoring AmberClaw database snapshots, WAL logs, and session stores following catastrophic storage corruption, host failure, or accidental data loss.

## Prerequisites
- Most recent encrypted backup snapshot archive located in storage backup directory (e.g. `~/.AmberClaw/backups/`).
- Valid backup manifest with SHA-256 integrity checksums.

## Procedure

### 1. List Available Backups
```bash
amberclaw backup list
```

### 2. Run Pre-Restoration Verification (DR Drill)
Verify that the backup manifest passes tamper-evidence checks before touching live storage:
```bash
amberclaw backup drill --backup-file ~/.AmberClaw/backups/snapshot_latest.tar.gz
```
Expected output:
```
Integrity check passed. Snapshot is valid and non-corrupted.
```

### 3. Stop AmberClaw Services
```bash
systemctl stop amberclaw-gateway
# or
docker compose -f deploy/docker/docker-compose.prod.yml down
```

### 4. Execute Restoration
```bash
amberclaw restore run --backup-file ~/.AmberClaw/backups/snapshot_latest.tar.gz --target-dir ~/.AmberClaw/
```

### 5. Verify Database Integrity & Start Services
```bash
amberclaw doctor
systemctl start amberclaw-gateway
```
Verify that the gateway responds to `/health` and that active agents load cleanly.
