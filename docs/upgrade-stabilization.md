# Stabilization upgrade and rollback guide (unreleased)

This is an operator review draft for the working tree based on `b83e63a`.
No release tag, signed artifact, publication or target deployment exists for it.
Resolve the dependency audit and remaining acceptance gates before release.

## Prepare

Record the installed revision, configuration, provider credentials' storage
locations and database backend. Stop every writer during a restore, using the
deployment's actual service manager. Back up files and SQLite state using the
[recovery runbook](runbooks/disaster_recovery_runbook.md). PostgreSQL requires its
own verified backup/restore procedure; the file-backup manager does not back up a
remote PostgreSQL database. Keep the previous executable environment and its
lockfile together with the matching pre-upgrade data snapshot.

In an isolated checkout of the reviewed candidate, use the committed lockfile:

```bash
uv sync --frozen
LITELLM_LOCAL_MODEL_COST_MAP=True make check
LITELLM_LOCAL_MODEL_COST_MAP=True uv run pytest -q
LITELLM_LOCAL_MODEL_COST_MAP=True uv run python examples/release_drill.py
```

The final command creates only disposable local SQLite state. It checks upgrade,
backup, data restore, schema rollback and re-upgrade, then removes that temporary
directory. It is not a target deployment or PostgreSQL acceptance check.

## Behavior changes to review

- Configure `JWT_SECRET_KEY`, `AUTH_CLIENT_ID` and `AUTH_CLIENT_SECRET` explicitly.
  The two secrets must be independent random values of at least32 bytes. Public
  default credentials and the old JWT signing fallback are rejected. Credential
  administration endpoints require an authenticated administrator; refresh
  tokens cannot authorize ordinary API requests. Reissue tokens after changing
  the signing key.
- SSO defaults to disabled. Configure a trusted IdP and exact HTTPS callback URL
  using [the SSO guide](sso.md). Unsigned SAML, unsolicited assertions and raw
  OIDC claims now fail authentication. Existing integrations must start a
  browser-bound login and return its state. This intentional security change
  breaks the former insecure callback contract.
- SSH requires a trusted host key in the user's known-hosts configuration.
  Verify and provision the key before connecting; unknown keys are rejected.
- Backup restores reject links, devices, traversal, duplicate/unlisted files and
  mismatched hashes before destination writes. Old malformed snapshots must be
  investigated rather than bypassing these checks.
- Unsupported blueprint policies fail before configuration loading/saving.
  Complete preset runtime enforcement remains open.
- The private dashboard requires explicit credentials and application services.
  Unavailable chat returns503. Do not replace that response with fabricated data.

## Target acceptance

Test the selected database upgrade and rollback on a copy of target data. Verify
real provider/channel connections, proxy HTTPS handling, SSO/certificate rotation,
chosen sandbox isolation, health checks and the deployment's performance budget.
The local SQLite drill and mocked contracts do not establish these outcomes.
Multi-worker SSO requires session affinity or an accepted shared atomic request
store. Do not publish provenance or sign artifacts before the final reviewed
source, dependency lock and actual artifact hashes are fixed.

## Roll back

Stop all writers. Restore the previous executable environment and its matching
lockfile. Restore the corresponding pre-upgrade data/configuration snapshot into
a separate directory and verify it before replacing live state. A schema downgrade
alone does not recover deleted or changed application data. Restart the actual
deployment only after its health, authentication and data checks pass. Record the
target evidence; deployment rollback remains unverified by this local work.
