# Security Policy & Architecture

## Reporting Vulnerabilities

Found a security hole in AmberClaw? Here is how to report it:

1. **Do not** open a public GitHub issue.
2. File a private security advisory on GitHub, or reach out directly to the maintainers.
3. Include in your report:
   - Vulnerability classification (e.g., SSRF, privilege escalation, bypass)
   - Step-by-step reproduction instructions or proof-of-concept
   - Impact assessment
   - Remediation suggestion

We target a 24 to 48-hour initial response time for all security inquiries.

---

## Zero-Trust Security Architecture & Threat Model

AmberClaw implements a layered **Zero-Trust Security Stack**:

```
[ Untrusted External Ingress ] -> (Channel Quarantine / PromptGuard / DLP)
                                       │
                                       ▼
                             [ API Gateway (mTLS 1.3) ]
                                       │
                                       ▼
                       [ RBAC / ABAC + Policy Lock Engine ]
                                       │
                                       ▼
                         [ Subagent Runtime Sandbox ]
                         ├─ Linux Namespaces (unshare)
                         ├─ Seccomp BPF Syscall Filters
                         ├─ Ephemeral Filesystem Isolation
                         ├─ DecompressionGuard (Anti-Zip Bomb)
                         └─ HostSocket & Metadata Filter (SSRF/IMDS)
                                       │
                                       ▼
                          [ Data & Secret Layer ]
                          ├─ Envelope Encryption (AES-256-GCM)
                          ├─ Pluggable KMS (AWS/GCP/Azure/Local)
                          ├─ Memory Safety & Wiping (memset)
                          └─ Tamper-Evident SHA-256 Hash Chain
```

### Trust Boundaries
1. **User & External Ingress**: All prompts, documents, web pages, MCP tools, and external channel inputs are treated as untrusted data (`<untrusted_content>` quarantine).
2. **Control vs Data vs Sandbox Networks**: Pods and containers run on segmented networks. Sandboxes have no network access by default (`CLONE_NEWNET`, K8s NetworkPolicy default-deny).
3. **Host Isolation**: Ephemeral workspaces prevent path traversal; Unix sockets (`docker.sock`) and cloud instance metadata (`169.254.169.254`) are systematically denied.
4. **Supply Chain**: Dependency lock pinning via `uv.lock`, automated CycloneDX and SPDX SBOM generation, and container image signing via Sigstore/Cosign.

---

## Security Features & Controls

### 1. Identity, Access Management & Admin MFA
- **OIDC / OAuth 2.1**: User authentication with rotating short-lived JWT access tokens and revocation store.
- **Hardware-Backed Admin MFA**: WebAuthn / FIDO2 security keys (YubiKey) with monotonic counter rollback detection, user presence, and single-use TOTP fallback.
- **Service-to-Service mTLS**: TLS 1.3 mutual authentication across all internal services and A2A agents.
- **Just-in-Time Elevation & Break-Glass**: Audited administrative privilege escalation with mandatory justification.

### 2. Sandbox Hardening
- **Process Isolation**: Linux user, network, mount, IPC, and UTS namespaces.
- **Syscall Blocking**: Seccomp BPF filters blocking unauthorized `execve` and `ptrace` syscalls.
- **Decompression Guard**: Defense against zip bombs, tar bombs, zip-slip directory traversal, and malicious symlink attacks.
- **Host Socket & SSRF Filter**: Blocks Unix domain sockets (`/var/run/docker.sock`) and RFC 1918 / cloud metadata IP addresses (`169.254.169.254`).

### 3. Data Protection, DLP & Retention
- **Policy Lock Engine**: Prevents untrusted retrieved content or indirect prompt injection from expanding tool permissions.
- **Data Loss Prevention (DLP)**: Automatic in-flight redaction of API keys, tokens, credit cards, and SSNs. Outbound transmission of private data requires operator confirmation tokens.
- **Envelope Encryption**: AES-256-GCM per-record encryption with pluggable KMS backends (AWS KMS, GCP Cloud KMS, Azure Key Vault, Local).
- **Memory Zeroing**: Sensitive credentials and cryptographic keys are explicitly overwritten with zeros (`ctypes.memset`) immediately after use.
- **GDPR / CCPA & Legal Hold**: Right-to-be-forgotten deletion cascades and cryptographic export archives, with evidentiary legal hold safeguards.

### 4. Supply Chain & CI/CD Security
- **Pinned Dependencies**: Pinned via deterministic `uv.lock`.
- **SBOM Generation**: Automated CycloneDX 1.5 and SPDX 2.3 bill of materials.
- **Signed Releases**: Sigstore / Cosign container image signatures and SLSA build provenance attestations.
- **Restricted CI**: GitHub Actions workflows run with `permissions: contents: read` and action versions pinned to commit SHAs.

---

## Incident Response Procedures

If a security incident or compromised credential is suspected:

1. **Immediate Revocation**:
   ```bash
   # Revoke all active API keys and tokens
   amberclaw auth revoke-all --user <user_id>
   ```
2. **Rotate Secrets Without Restart**:
   ```bash
   amberclaw vault rotate --secret-name <NAME>
   ```
3. **Inspect Tamper-Evident Audit Chains**:
   ```bash
   amberclaw audit verify --log-file logs/audit.jsonl
   ```
4. **Trigger Emergency Break-Glass**:
   ```bash
   amberclaw admin break-glass --reason "Investigating security incident"
   ```
5. **Contact Security Team**: File a private advisory on GitHub or email security@amberclaw.ai.

---

## License

See [LICENSE](file:///home/ai/Documents/projects/Freelance/AmberClaw/LICENSE) for details.
