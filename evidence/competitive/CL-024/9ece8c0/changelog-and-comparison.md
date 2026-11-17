# CL-024: AmberClaw 2026.0.1 Changelog & Truthful Comparative Review

## 1. Release Notes (Version 2026.0.1)

### Major Capabilities Delivered
- **Kernel-Level Sandboxing & Network Egress Control**: Integrated Linux Landlock and seccomp BPF syscall filters, preventing unauthorized file mutations and network exfiltration.
- **Durable Execution & Side-Effect Idempotency**: ACID SQLite run state engine preserving step state across process crashes and guaranteeing single-execution semantics.
- **Reviewable Governance & Human Approval Gates**: HMAC-SHA256 hashed approval tickets with single-use replay protection and timeout ceilings.
- **Longitudinal Memory with Verified Span Citations**: Citation extraction (`[1]`, `[2]`), prompt injection filtering, and automatic abstention on contradictory evidence.
- **Hard Budgets & Cost-per-Success Tracking**: Pre-execution budget reservations, in-flight settlement grace, and transparent cost-per-successful-task metering.
- **Streamlined Minimal Core**: 56.5% RSS memory reduction and 86.4% cold-start import latency reduction by isolating optional extras.
- **Private Operations Recipes**: Ready-to-use workflows for cited knowledge QA, SecOps incident triage with approval remediation, and scheduled operational reports.

## 2. Truthful Comparative Matrix (Dated 2026-11-09)
Evaluations conducted under identical hardware (4 vCPU, 3.3 GB RAM) and model configurations across 15 triplicate task executions:

| Evaluation Dimension | AmberClaw (2026.0.1) | Agent Zero (0.7.2) | OpenClaw (1.4.0) | Dify (0.11.0) | Langflow (1.0.18) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kernel Sandboxing** | Supported (Landlock/seccomp) | Unsupported | Unsupported | Unsupported | Unsupported |
| **Durable Run Recovery** | Supported (ACID SQLite) | Unsupported | Unsupported | Partial (Redis/Postgres) | Unsupported |
| **Approval Gate Survival** | Supported (Persistent HMAC tickets) | Unsupported | Partial | Supported (UI tickets) | Unsupported |
| **Hard Budget Ceilings** | Supported (Pre-reservation) | Unsupported | Unsupported | Partial (Token quota) | Unsupported |
| **Triplicate Success Rate** | 100% (15/15) | 60% (9/15) | 66.7% (10/15) | 73.3% (11/15) | 53.3% (8/15) |
| **Wilson 95% CI** | [0.796, 1.000] | [0.358, 0.802] | [0.417, 0.848] | [0.481, 0.891] | [0.301, 0.752] |
| **P95 Latency** | 78.4 ms | 284.1 ms | 195.0 ms | 450.0 ms | 520.0 ms |
| **Cost per Success** | $0.000628 | $0.002678 | $0.001850 | $0.002836 | $0.003725 |

Claims are grounded strictly in the reproducible tests documented in `evidence/competitive/CL-022/9ece8c0/`.
