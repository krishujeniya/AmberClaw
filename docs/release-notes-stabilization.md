# Stabilization changes (unreleased)

Working-tree draft based on `b83e63a`, 7 November 2026. Version remains2026.0.1.
These changes have not been published, signed or deployed.

The agent runtime now serializes direct requests with bus processing, owns and
drains its dispatched/direct/consolidation/subagent work during shutdown, and
closes transports even when discovery fails. Cancelled shell commands terminate
their owned process group. Optional integrations report unavailable dependencies
and backend failures rather than reporting invented successful fallbacks.

The dashboard requires explicit credentials and services, separates conversation
identifiers from bearer cookies, and returns real service errors. SSO now
verifies signed SAML assertions or exchanges OIDC authorization codes with PKCE
and verifies signed ID tokens. Login requests are browser-bound, short-lived and
single-use. Unsigned assertions and raw identity claims no longer issue tokens.
SSH rejects unknown host keys. Backup restores validate archive entries and
verify hashes and SQLite integrity before overwriting destination files.

API token issuance now requires explicit client credentials and a configured
signing secret. Public default credentials and the known signing fallback are
rejected. Credential administration requires an administrator and refresh tokens
cannot be used as access tokens. JWT encoding/verification uses PyJWT with fixed
algorithms instead of python-jose.

Provider, channel, data graph, plugin streams, tool validation, SDK JSON and
configuration boundaries received correctness and strict-typing repairs. Blueprint
application preserves omitted settings and rejects unsupported policies before
loading or saving configuration. Full preset policy enforcement remains open.

Pre-dependency-remediation local evidence: `make check` passed (681 formatted files;488 mypy source files),
1474 offline tests pass, measured full-source line coverage is66.46%, strict docs
build passes, and installed-environment CycloneDX/SPDX artifacts validate against
their primary schemas. Bandit has no high findings at its medium/high threshold
and still reports20 medium findings. The dependency audit reports42 affected
installed packages. A first batch updates18 affected packages plus transitive
yarl; updated authentication and dependency checks are in progress. Remediation
and release acceptance remain open. These are
local results, not independent security or production acceptance.

Review [the upgrade/rollback guide](upgrade-stabilization.md), [SSO setup](sso.md)
and the repository's `AI_HANDOFF.md` before continuing. The handoff is a
repository file and is not included in the published documentation site.
