# CL-023: Independent Security Acceptance & Threat Model

## 1. Scope of Independent Security Review
This review evaluates AmberClaw's security controls against the OWASP Top 10 for Large Language Model Applications (2025/2026) and agentic execution threats:

1. **LLM01: Prompt Injection**: Direct and indirect prompt injection attempts seeking to alter agent instructions or bypass safety boundaries.
2. **LLM02: Sensitive Information Disclosure**: Secret leakage, API token exposure, PII extraction, and unredacted logging.
3. **LLM06: Excessive Agency**: Unrestricted tool execution, missing human approval for destructive mutations, and runaway infinite execution loops.
4. **LLM07: System Prompt & Instruction Leakage**: Exfiltration of internal operating policies, system directives, or operator identity tokens.
5. **LLM08: Vector and Embedding Poisoning**: Contradictory, poisoned, or malicious context documents stored in long-term memory.
6. **LLM09: Misinformation & Hallucination**: Unsubstantiated claims, fabricated evidence, and absence of verifiable span citations.
7. **LLM10: Unbounded Consumption & Denial of Service**: Runaway token usage, infinite tool loops, and uncontrolled CPU/memory exhaustion.

## 2. Review Boundaries & Components Tested
- **Kernel Sandbox Boundaries**: Linux Landlock V1-V3 ABI filesystem sandboxing, seccomp BPF syscall filtering, namespace isolation.
- **Egress & Network Containment**: Network policy matchers, DNS interception, TLS-only restrictions, SSRF blocklists for cloud metadata endpoints (`169.254.169.254`).
- **Tenant & Path Isolation**: Zero cross-tenant data leakage, directory traversal (`../`) prevention, tar-slip archive validation.
- **Human Approval & Governance**: HMAC-SHA256 argument hashing, single-use ticket consumption, ticket expiration, identity binding.
- **Secrets & Token Lifecycle**: Dynamic secrets rotation, persistent session revokelists, key retirement.
- **Crash Recovery & Side-Effect Idempotency**: State reconciliation without duplicate remote mutations.
