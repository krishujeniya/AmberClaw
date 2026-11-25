# CL-026: Extension Ecosystem Maintainer Governance Process

## 1. Governance Principles
To ensure third-party extensions do not compromise system boundaries, isolation guarantees, or secret boundaries, every curated extension in the AmberClaw ecosystem must undergo structured maintainer review before listing or inclusion.

## 2. Review Stages
All extension pull requests and submissions follow a 4-stage pipeline:

1. **Automated Static Scan**:
   - Manifest validation against `PluginManifest` schema.
   - AST inspection of entrypoint scripts for forbidden imports (`ctypes`, raw memory mutation, raw socket calls bypassing Landlock).
   - Credential leak check (ensure no hardcoded tokens or API keys).
2. **Automated Conformance Suite**:
   - Execution within an isolated ephemeral Docker runner with Landlock and network namespace restrictions.
   - Verification that declared capabilities match actual system calls.
   - Verification that medium/high risk actions generate pending `ApprovalTicket` instances.
   - Verification that manifest removal revokes all registered tools immediately.
3. **Manual Code & Capability Audit**:
   - Minimum two maintainer approvals.
   - Scrutiny of external network dependencies and destination hostnames.
   - Validation that data payloads do not log raw prompt contexts or tenant identifiers.
4. **Cryptographic Signing**:
   - Approved plugins are signed with the AmberClaw Release Key (`cosign` / minisign).
   - Checksum and signature appended to the official plugin registry catalog.

## 3. Security Vulnerability & Revocation SLA
- **Critical / High CVEs**:
  - Response SLA: 24 hours.
  - Revocation: Remote revocation list published to registry within 4 hours of confirmed exploitation.
  - Active daemon action: Client instances auto-disable revoked plugin hashes upon next registry sync.
- **Medium / Low Issues**:
  - Patch window: 14 days.
  - If unpatched within window, extension is flagged as `deprecated` and hidden from default listing.

## 4. Semver & Compatibility Policy
- Extensions declare `min_amberclaw_version` and supported core major versions.
- Core runtime breaking changes require a minimum 6-month deprecation notice and transition adapter.
