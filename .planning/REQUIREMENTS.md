# Requirements - Milestone 9: MCP, Protocols & Tool Ecosystem

## AC-093 | Upgrade MCP to Latest 2026 Specification
- **Description**: Ensure compatibility with the latest Model Context Protocol spec, including newer transports and enterprise features.
- **Acceptance**: MCP servers using the 2026 spec connect and function correctly.

## AC-094 | Add A2A (Agent-to-Agent) Protocol Support
- **Description**: Implement the Agent-to-Agent protocol for inter-agent communication and collaboration.
- **Acceptance**: Two AmberClaw instances can discover and message each other via A2A.

## AC-095 | Implement MCP Server Discovery and Dynamic Registration
- **Description**: Auto-discover available MCP servers on the network and register their tools dynamically.
- **Acceptance**: New MCP server appears in tool list without config restart.

## AC-096 | Build Built-In Web Search Tool
- **Description**: Bundle a web search tool using Tavily, Brave Search API, or SerpAPI that works out-of-the-box without MCP configuration.
- **Acceptance**: `search_web("query")` tool works immediately after setting an API key.

## AC-097 | Deepen ClawHub / OpenClaw Compatibility
- **Description**: Full support for discovering, installing, and running SKILL.md-based skills from the ClawHub registry.
- **Acceptance**: `amberclaw skill install clawhub:skill-name` works end-to-end.

## AC-098 | Add CLI Skill Install Command
- **Description**: Implement `amberclaw skill install <url/slug>` with dependency resolution and verification.
- **Acceptance**: CLI can install a skill from GitHub URL or ClawHub slug.

## AC-099 | Support Standard Tool Formats Beyond MCP
- **Description**: Support OpenAI function calling, Anthropic tool use, and LangChain tool formats natively.
- **Acceptance**: Tools defined in any of these formats execute without wrapper translation.

## AC-100 | Create Curated, Security-Verified Skill Collection
- **Description**: Maintain an official list of vetted skills with security badges and version pinning.
- **Acceptance**: Curated registry exists with ≥10 verified skills.

## AC-101 | Add Skill Security Scanning Before Loading
- **Description**: Scan skills for prompt injection, credential exfiltration, and malicious shell commands before execution.
- **Acceptance**: Loading a malicious skill is blocked and logged.

## AC-102 | Add Skill Versioning and Marketplace Infrastructure
- **Description**: Support skill versioning, dependency management, and a community marketplace with ratings.
- **Acceptance**: Skills can specify version ranges and dependencies; marketplace UI exists.

## AC-103 | Fix Dockerfile to Run as Non-Root User
- **Description**: Add a `USER` directive in the Dockerfile final stage; do not run as root.
- **Acceptance**: Container runs as UID ≥1000; `whoami` inside container returns non-root.

## AC-104 | Encrypt API Keys at Rest
- **Description**: Use the existing `keyring` dependency to store API keys in the OS credential store instead of plaintext `~/.AmberClaw/config.json`.
- **Acceptance**: Config file contains no plaintext API keys; keys are retrieved from OS keyring.

## AC-105 | Add PII Detection and Redaction
- **Description**: Integrate Presidio or similar to detect and redact personally identifiable information in logs and memory.
- **Acceptance**: PII (emails, phone numbers, SSNs) is redacted in all persistent storage.

## AC-106 | Implement Sandboxed Code Execution
- **Description**: Run shell/code tools inside Firejail, gVisor, or a disposable Docker container instead of the host.
- **Acceptance**: A malicious `rm -rf /` command inside a tool is contained and cannot harm the host.

## AC-107 | Add Structured, Immutable Audit Logs
- **Description**: Log every tool execution, API key access, and config change to an append-only, tamper-evident log.
- **Acceptance**: Audit log cannot be modified by the application user; entries are cryptographically chained or WORM-stored.

## AC-108 | Support Role-Based Access Control (RBAC)
- **Description**: Replace binary allow/block with roles (admin, user, guest) that have different permission sets.
- **Acceptance**: Config supports role definitions; agent enforces role-based tool access.

## AC-109 | Add Secret Scanning Prevention in Logs
- **Description**: Ensure API keys and tokens are never printed in logs, tracebacks, or error messages.
- **Acceptance**: Log inspection reveals zero leaked secrets under normal and error conditions.

## AC-110 | Strengthen Tool Sandboxing and Default restrictToWorkspace
- **Description**: Set `restrictToWorkspace` default to `true`. Add warnings in docs for `allowFrom: ["*"]`. Strengthen MCP sandboxing with syscall filtering where possible.
- **Acceptance**: Fresh install is sandboxed; dangerous configs require explicit opt-in with warnings.

## AC-111 | Add Rate Limiting on Outgoing LLM Calls
- **Description**: Throttle cron/heartbeat and user-triggered requests to prevent provider rate limits and cost spikes.
- **Acceptance**: Burst of 100 requests is smoothed to provider-safe rates; user can configure RPM limits.

## AC-112 | Add Input Sanitization and Output Filtering
- **Description**: Sanitize all channel inputs and filter outputs for dangerous content (prompt injection, XSS, control characters).
- **Acceptance**: Known prompt injection payloads are neutralized.

## AC-113 | Disclose WhatsApp Node.js Subprocess Risks
- **Description**: Document that the WhatsApp integration spawns an unaudited Node.js process and advise on isolation.
- **Acceptance**: SECURITY.md and README contain a clear disclosure about WhatsApp bridge risks.

## AC-114 | Add SLSA Provenance and SBOM Generation
- **Description**: Generate signed build attestations and a Software Bill of Materials for every release.
- **Acceptance**: Release artifacts include `.provenance` and `.sbom.json` files.

## AC-115 | Support External Secret Management
- **Description**: Allow integration with 1Password, HashiCorp Vault, or environment variables for secrets instead of config files.
- **Acceptance**: Agent starts successfully with all secrets provided via env vars or vault references.
