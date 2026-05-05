# Roadmap

## Milestone: v1.0 Production Reliability & Architecture

| Phase | Name | Goal | Status |
|-------|------|------|--------|
| 1 | Unification Completion | Refactor all tools to Pydantic v2 and stabilize build system. | ✓ Done |
| 2 | Memory & RAG Integration | Implement Mem0 v1.0+ and persistent vector storage. | ✓ Done |
| 3 | Advanced Infra & CLI | Implement AmberClaw Doctor, async I/O, and parallel tools. | ⏺ Active |
| 4 | Enterprise Features | MCP integration, RBAC, and advanced security. | ⏺ Planned |

---

## Phase Detail

### Phase 1: Unification Completion
- ✓ Switch to Hatchling build system
- ✓ Refactor Council/Mythos to PydanticTool
- ✓ Strict type-safety with mypy/pyright

### Phase 2: Memory & RAG Integration
- ✓ Mem0 v1.0+ core implementation
- ✓ ChromaDB/LanceDB backend support
- ✓ Temporal Knowledge Graph extraction
- ✓ Multi-scope memory (user, agent, session)

### Phase 3: Advanced Infra & CLI
- [ ] **AmberClaw Doctor**: System health check command
- [ ] **Async Data Operations**: Background thread I/O for Pandas
- [ ] **Parallel Tool Execution**: asyncio.TaskGroup orchestration
- [ ] **Unified Messaging Bus**: Multi-channel routing enhancements

### Phase 4: Enterprise Features
- [ ] MCP Server Support
- [ ] Role-Based Access Control (RBAC)
- [ ] PII Detection and Redaction
- [ ] Sandboxed Code Execution

## Milestone: v1.1 LLM Providers, Models & Routing

| Phase | Name | Goal | Status |
|-------|------|------|--------|
| 5 | LLM Core Intelligence | Fix models, add providers, and capability detection. | ⏺ Planned |
| 6 | Reliability & Observability | Fallback routing, cost tracking, and monitoring. | ⏺ Planned |
| 7 | Performance & Local Ops | Streaming, caching, and Ollama optimizations. | ⏺ Planned |

---

## Phase Detail

### Phase 5: LLM Core Intelligence
- [ ] Fix default model names (AC-080, AC-081)
- [ ] Add missing providers (xAI, Cohere, Mistral, Bedrock, NIM) (AC-082)
- [ ] Implement capability detection (Vision, JSON, Tools) (AC-083)
- [ ] Enforce structured outputs for tools (AC-088)

### Phase 6: Reliability & Observability
- [ ] Automatic provider fallback routing (AC-084)
- [ ] Per-provider/session cost tracking (AC-085)
- [ ] Token usage monitoring CLI/metrics (AC-086)
- [ ] Latency monitoring (TTFT, Total) (AC-090)

### Phase 7: Performance & Local Ops
- [ ] Streaming response support (AC-089)
- [ ] Multi-provider prompt caching (AC-087)
- [ ] Ollama Quickstart guide (AC-091)
- [ ] Local model optimizations (GGUF, LoRA) (AC-092)

## Milestone: v1.2 MCP, Protocols & Tool Ecosystem

| Phase | Name | Goal | Status |
|-------|------|------|--------|
| 8 | Protocol Upgrades & Discovery | Upgrade MCP to 2026, add A2A and dynamic registration. | ⏺ Planned |
| 9 | Tooling & Skill Registry | Web search, ClawHub compatibility, and standard formats. | ⏺ Planned |
| 10 | Marketplace & Security | Curated registry, security scanning, and marketplace. | ⏺ Planned |
| 11 | Security, Safety & Compliance | Docker, Keyring, PII, Sandboxing, Audit Logs, RBAC. | ⏺ Planned |
| 12 | Observability & Tracing | OpenTelemetry, LLM tracing, Eval suite, Cost tracking. | ⏺ Planned |
| 13 | Deployment & Scaling | Slim images, Healthchecks, K8s, Redis, Horizontal scaling. | ⏺ Planned |
| 14 | Channels & Web UI | Web UI, More platforms, Productivity integrations. | ⏺ Planned |
| 15 | Automation & Workflows | Visual builder, Proactive behaviors, DAG engine. | ⏺ Planned |
| 16 | Performance & Edge | ARM/RPi optimization, Streaming, Interactive CLI. | ⏺ Planned |
| 17 | Community & Ecosystem | Project website, Tutorials, ClawHub, MLOps, Documentation. | ⏺ Planned |

---

## Phase Detail

### Phase 8: Protocol Upgrades & Discovery
- [ ] Upgrade MCP to Latest 2026 Specification (AC-093)
- [ ] Add A2A (Agent-to-Agent) Protocol Support (AC-094)
- [ ] Implement MCP Server Discovery and Dynamic Registration (AC-095)

### Phase 9: Tooling & Skill Registry
- [ ] Build Built-In Web Search Tool (AC-096)
- [ ] Deepen ClawHub / OpenClaw Compatibility (AC-097)
- [ ] Add CLI Skill Install Command (AC-098)
- [ ] Support Standard Tool Formats Beyond MCP (AC-099)

### Phase 10: Marketplace & Security
- [ ] Create Curated, Security-Verified Skill Collection (AC-100)
- [ ] Add Skill Security Scanning Before Loading (AC-101)
- [ ] Add Skill Versioning and Marketplace Infrastructure (AC-102)

### Phase 11: Security, Safety & Compliance
- [ ] Fix Dockerfile to Run as Non-Root User (AC-103)
- [ ] Encrypt API Keys at Rest (AC-104)
- [ ] Add PII Detection and Redaction (AC-105)
- [ ] Implement Sandboxed Code Execution (AC-106)
- [ ] Add Structured, Immutable Audit Logs (AC-107)
- [ ] Support Role-Based Access Control (RBAC) (AC-108)
- [ ] Add Secret Scanning Prevention in Logs (AC-109)
- [ ] Strengthen Tool Sandboxing and Default restrictToWorkspace (AC-110)
- [ ] Add Rate Limiting on Outgoing LLM Calls (AC-111)
- [ ] Add Input Sanitization and Output Filtering (AC-112)
- [ ] Disclose WhatsApp Node.js Subprocess Risks (AC-113)
- [ ] Add SLSA Provenance and SBOM Generation (AC-114)
- [ ] Support External Secret Management (AC-115)

### Phase 12: Observability, Evaluation & Tracing
- [ ] Integrate OpenTelemetry for Distributed Tracing (AC-116)
- [ ] Add LLM Tracing Integration (Langfuse / Phoenix / Traceloop) (AC-117)
- [ ] Create Evaluation Suite Using LLM-as-a-Judge (AC-118)
- [ ] Add Cost Tracking Dashboard (AC-119)
- [ ] Add Latency Monitoring for Tool Calls (AC-120)
- [ ] Add Prometheus Metrics Endpoint (AC-121)
- [ ] Add Performance Benchmarking Against Competitors (AC-122)
- [ ] Implement RAGAS-Based Retrieval Evaluation (AC-123)

### Phase 13: Deployment, Scaling & Infrastructure
- [ ] Separate Slim / Gateway-Only Docker Image (AC-124)
- [ ] Add HTTP Healthcheck Endpoint (AC-125)
- [ ] Add GitHub Actions for GHCR Publishing (AC-126)
- [ ] Add Multi-Architecture Docker Builds (AC-127)
- [ ] Add Kubernetes Helm Charts (AC-128)
- [ ] Support PostgreSQL as Alternative to SQLite (AC-129)
- [ ] Add Redis for Distributed State and Pub/Sub (AC-130)
- [ ] Create Serverless Deployment Examples (AC-131)
- [ ] Support Environment Variables for Secrets (AC-132)
- [ ] Add Horizontal Scaling Support for Gateway (AC-133)
- [ ] Enhance Docker Compose with Profiles and Healthchecks (AC-134)
- [ ] Improve Systemd Service Template (AC-135)

### Phase 14: Channels, Integrations & Web UI
- [ ] Add Self-Hosted Web UI (AC-136)
- [ ] Add More Chat Platforms (AC-137)
- [ ] Improve WhatsApp Bridge Reliability (AC-138)
- [ ] Add Calendar and Productivity Integrations (AC-139)
- [ ] Add Google Workspace and Email Automation (AC-140)
- [ ] Add Smart Home Integration Hooks (AC-141)
- [ ] Improve Unified Messaging Bus (AC-142)
- [ ] Support Voice Channels Beyond Text (AC-143)

### Phase 15: Automation, Cron & Workflows
- [ ] Expand Cron/Heartbeat with Visual Workflow Builder (AC-144)
- [ ] Add Proactive Agent Behaviors (AC-145)
- [ ] Add Third-Party Automation Integrations (AC-146)
- [ ] Implement Multi-Step Workflow Engine (AC-147)

### Phase 16: Performance, Edge & Usability
- [ ] Optimize for Low-Resource and Edge Devices (AC-148)
- [ ] Add Streaming with Typing Indicators (AC-149)
- [ ] Improve CLI with Interactive Features (AC-150)
- [ ] Benchmark Against Competitor Frameworks (AC-151)
- [ ] Add Simple Desktop App Wrapper (AC-152)
- [ ] Optimize Gateway for Concurrent Long-Running Sessions (AC-153)

### Phase 17: Community, Ecosystem & Adoption
- [ ] Create Dedicated Project Website with Live Demo (AC-154)
- [ ] Publish Tutorials, Blog Posts, and Video Content (AC-155)
- [ ] Engage OpenClaw / ClawHub Community (AC-156)
- [ ] Target Privacy-Focused Users with Local-First Guides (AC-157)
- [ ] Label Good First Issues and Offer Skill Bounties (AC-158)
- [ ] Monitor AI Agent Trends and Adapt Quickly (AC-159)
- [ ] Highlight Ultra-Lightweight Positioning in Marketing (AC-160)
- [ ] Add Research-Oriented Modules (CV / NLP / GenAI) (AC-161)
- [ ] Add MLOps Features (Experiment Tracking, A/B Testing) (AC-162)
- [ ] Add Comprehensive Inline Code Comments (AC-163)
- [ ] Add Input Validation and Graceful Error Handling (AC-164)
