# Sandbox Containment Threat Model and Attestation Protocol (CL-006 / Observation A06)

## 1. Threat Scenarios and Mitigations

| Threat ID | Threat Vector | Target Asset | Defense Layer | Mitigation & Containment Behavior |
|---|---|---|---|---|
| **THREAT-01** | Path Traversal / Escape | Host filesystem (`/etc`, `/root`, SSH keys) | Landlock LSM + Ephemeral Sandboxing | Read/write restricted to workspace and `/tmp`. Traversal attempts raise `PermissionError`. |
| **THREAT-02** | Subprocess Execution Escape | Shell utilities, compiler toolchains | Seccomp BPF syscall filters | `block_execve=True` enforces seccomp filter denying `execve` and `ptrace` with `EACCES`. |
| **THREAT-03** | Network Egress & SSRF | Internal network, Cloud metadata (`169.254.169.254`) | Linux network namespace (`CLONE_NEWNET`) + `HostSocketAndMetadataFilter` | Zero egress routes inside container; loopback, private CIDRs, and metadata hostnames blocked. |
| **THREAT-04** | Container Socket Hijack | Docker/containerd UNIX domain sockets (`docker.sock`) | Socket path filtering + User namespaces | Host container orchestrator sockets blocked; unprivileged user namespace drops root capabilities. |
| **THREAT-05** | Archive Bomb & Zip-Slip | Host disk space and path overwrites | `DecompressionGuard` | Compression ratio ceiling (100:1), maximum uncompressed bytes (50MB), symlink rejection, path traversal checks. |
| **THREAT-06** | Resource Exhaustion (DoS) | Host memory, CPU, process table | Linux `setrlimit` | Hard ceilings: 512MB address space, 30s CPU time, 10 max processes, 10MB maximum created file size. |

## 2. Containment Modes

### Strict Mode (`strict=True`)
Refuses code execution if any required kernel containment mechanism is unavailable or rejected by the host:
- Landlock LSM unsupported -> aborts with `SandboxContainmentError`.
- Seccomp filter rejection -> aborts with `SandboxContainmentError`.
- Non-Linux environment without Docker -> aborts with `SandboxContainmentError`.
- Exit code 126 and structured containment error emitted. Untrusted code is never run unconfined.

### Degraded Mode (`strict=False`)
Permits best-effort containment on older kernels or unprivileged containers, returning a `ContainmentAttestation` object with active flags and an explicit `limitations` array detailing missing kernel capabilities.
