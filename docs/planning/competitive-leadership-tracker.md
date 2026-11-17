# AmberClaw competitive leadership tracker

Research checkpoint: **8 November 2026**. Checkout: `main`, `9ece8c02f4ce31178bed489ca07f26af29d6d735`. Working tree was clean at review start. Deliverable: research and planning, not a product release.

## Decision and intended outcome

AmberClaw should compete first as a **private, auditable automation runtime for small developer and operations teams**. Its README already identifies private automation, developers/teams, tools, sandboxes and messaging as the offer. Narrowing the initial buyer to small teams and the initial jobs below is a proposed strategy, not validated customer demand.

Build the most dependable path from an authenticated request to a permitted, completed, recoverable action. Start with three workflows: cited internal-document answers; incident investigation with a human-approved remediation; scheduled report generation with an approved channel delivery. Use synthetic data and mocked destinations until live access is explicitly authorized.

**No evidence currently establishes world number one.** This document selects 20 strategically relevant competitors, not a verified market-share ranking or an exhaustive census. Winning requires a defined segment, comparable task outcomes, external replication and customer adoption. Feature count, unit-test count, GitHub stars and vendor benchmark claims cannot establish overall leadership.

Immediate priorities:

1. Reconcile evidence and public claims, especially the existing unsourced comparison table.
2. Prove a single secured runtime across API, CLI, dashboard and channels.
3. Close policy-binding, containment, tenant-boundary and recovery acceptance gaps.
4. Measure task success, prohibited actions, latency and total cost under equal conditions.
5. Earn adoption with a small set of complete workflows, migration tools and honest operational documentation.

## How to use this tracker

This is the **new competitive strategy backlog**, separate from the historical stabilization queue in `../../.planning/tracker.md`. Do not reopen completed stabilization items automatically, mark these proposals delivered, or unfreeze older strategy work. On implementation approval, promote the lowest-numbered ready item into that execution queue and link its evidence here. Existing Definition of Done still applies.

Statuses: `READY` = planning complete and dependencies clear; `PLANNED` = dependent work; `EXTERNAL` = needs customer participation, paid execution, target access or independent review. The `VERIFIED` labels are claims recorded in the 8 November 2026 evidence set; they are not current verification of the dirty worktree. CL-001 is reopened for current claim/revision reconciliation. No GitHub Actions run for the present uncommitted changes has been inspected. The initial research checkpoint scoped these items as proposals; later evidence folders record completion claims that still require revision-specific reconciliation. Role owners below are proposed responsibilities, not assigned people. Effort bands: S = 1–3 engineer days; M = 4–10; L = 11–25; XL = discovery then re-estimate. These are planning estimates with substantial uncertainty.

Research uses the competitive-platform-analysis, benchmark-methodology, competitive-report-structure and deep-research skills, plus security-review, eval-harness and verification-loop. Their source/evidence discipline is adapted to software runtimes; branding-agency scores are not applicable. Unrelated skills were not executed. Research agents wrote temporary notes; the main agent is the sole repository writer. Available web browsing substituted for unavailable Exa/Firecrawl tooling.

## Evidence rules and comparison scope

- **S — source inspected:** repository implementation inspected locally; does not establish deployment behavior.
- **T — tested now:** explicitly executed checks in this research session, listed below.
- **R — recorded:** existing local logs/handoff; not rerun or independently attested.
- **D — documented:** official competitor documentation/repository says a feature exists. Not a hands-on result.
- **I — inference:** strategic advantage or proposed response inferred from documented capabilities.
- **U — unknown:** insufficient evidence; never treat as feature absence.

Primary sources were opened during this session; profile links identify the pages supporting each competitor's documented claims. Two pages owned by one vendor corroborate documentation, not independent effectiveness. No competitor was installed or benchmarked. Pricing/licensing descriptions are informational snapshots, not legal clearance; exact cost requires workload-specific measurement and current terms. Sources can change after this date; pin a release/commit before running comparisons. Do not infer a feature is missing because a selected page does not mention it.

Selection lens: deployment ownership, agent execution overlap, persistent state, tool access, workflow operations and buyer substitution. Direct assistants/runtime platforms, adjacent developer frameworks/workflow builders and an aspirational enterprise buying alternative are intentionally separated. No arbitrary composite score is used. Managed services are compared as buying alternatives, not as equal software libraries.

## AmberClaw: inspected baseline and gaps

| ID | Observation and evidence | Confidence / implication | Backlog |
|---|---|---|---|
| A01 | `AI_HANDOFF.md` names revision `1e5f571`; current HEAD is `9ece8c0`. `.planning/evidence/2026-11-08/checkpoint.json` still names `b83e63a`, 1,485 tests and 67.82% security branch coverage; the same day's `full-suite.txt` ends with 1,602 passes and the handoff reports 90.42% security branches. | S/R: inconsistent snapshots, not proof tests failed. Bind each claim to its exact source revision and command. | CL-001 |
| A02 | `src/amberclaw/blueprints/applier.py::_unsupported_runtime_settings` rejects prompt, memory nudge, skills and security settings lacking canonical consumers. `tests/unit/blueprints/test_runtime_application.py` explicitly expects all four full presets to fail closed. | S: safe rejection exists; full blueprint runtime support does not. | CL-005 |
| A03 | `src/amberclaw/api/v1/chat.py` calls `LLMRouter.generate/generate_stream` with system/user messages. `src/amberclaw/web/server.py` accepts optional `DashboardServices.runtime`; missing binding returns 503. ADR-0002 records this boundary. | S: multiple entry paths exist; full tool/memory/policy parity is unproven. Do not describe direct completion as full agent execution. | CL-004 |
| A04 | `tests/evals/test_agent_eval.py` defines three model-backed cases whose success condition is expected tool-name occurrence and no exception. `benchmarks/benchmark_suite.py` measures local components such as audit writes, FTS search and template rendering. | S: useful foundations, insufficient outcome/reliability/cost comparison. Model suite was not invoked. | CL-003, CL-015 |
| A05 | `tests/integration/test_integration_chat.py` configures three standalone MagicMocks and asserts their own return values. | S: those three tests do not exercise AmberClaw channel adapters. Other channel tests exist; this is not a claim all integration tests are mocks. | CL-010 |
| A06 | `src/amberclaw/security/sandbox.py` local setup suppresses some failures and logs skipped Landlock setup; seccomp returns are not enforced in that helper. | S: review required for strict-mode fail-closed behavior; no sandbox escape reproduced here. Platform/backend behavior needs separate proof. | CL-006 |
| A07 | `src/amberclaw/security/audit.py` reads last entry then appends a hash-chained record. No external anchor or writer coordination appears in this inspected path. README calls records immutable. | S/I: tamper evidence is not immutability; multi-process integrity and truncation detection require tests. No exploit claim. | CL-007 |
| A08 | Checkpoint records 45 remaining advisory records across 13 packages and 20 medium Bandit findings. | R: historical counts only; current reachability, inventory and remediation state are unverified. Conflicts with broad zero-gap wording. | CL-002 |
| A09 | `src/amberclaw/api/v1/router.py` protects application routes with `get_current_user`; tenant tests exist in storage and memory. Chat uses a module-level JSON agent store. | S: authentication exists; endpoint-to-storage tenant ownership still requires integrated negative tests. | CL-008 |
| A10 | Chat HTTP/SSE paths pass exception text into responses. `api/errors.py` redacts recognized secret patterns for HTTP errors. | S/I: patterned redaction does not establish confidentiality for arbitrary provider errors; verify both paths with canary values. | CL-009 |
| A11 | `pyproject.toml` includes data/scientific, provider, channel and storage dependencies in the base install; sandbox packages form a separate extra. | S: base-install size/attack surface should be measured before packaging decisions; no current footprint measured. | CL-016 |
| A12 | `docs/comparisons.md` contains uncited negative claims about rivals and calls FTS5 session storage tamper-evident memory. | S: comparison is not acceptable research evidence. FTS indexing alone does not supply integrity proof. | CL-001 |
| A13 | `src/amberclaw/agent/loop.py`, provider resilience, channel adapters, storage, security modules and observability code exist; selected boundary tests attempted below. | S: broad base to improve, not a reason to rewrite the framework. | All |

**What is not established:** production uptime, end-to-end breach resistance, independent security review, current live CI, model-backed task success, market leadership, user retention, real messaging delivery, comparative cost and target PostgreSQL/Kubernetes recovery. The old handoff contains conflicting completed/open release statements; none are silently resolved in this research task.

## Landscape map

Qualitative product map, not a scored performance chart. Products can span cells.

| | Developer-authored workflows | Ready-to-operate assistants / application platforms |
|---|---|---|
| Operator-controlled deployment emphasized | LangGraph, CrewAI, Microsoft Agent Framework, Google ADK, OpenAI Agents SDK, PydanticAI | AmberClaw target; OpenClaw, Nanobot, ZeroClaw, PicoClaw, Agent Zero, Agno; self-hosted Dify/n8n/Langflow; OpenHands development workflows |
| Managed experience or lifecycle transition matters | LangSmith managed services; framework cloud offerings | Microsoft Copilot Studio; Letta/Letta Code lifecycle; Open Interpreter current coding direction; archived Flowise migration reference |

Owning deployment and providing governance are already contested. The proposed opportunity is **measurably reliable private operations with inexpensive setup and evidence for every consequential action**. This is a hypothesis to test, not an empty market or unique moat.

## Twenty competitor profiles

The following profiles retain source links, documented capabilities, inferred advantage, deployment/commercial constraints and the concrete response. Numbering identifies entries, not popularity or quality rank.

## 1. OpenClaw — direct

**Documented features:** Self-hosted personal or shared gateway; messaging across Discord, iMessage, Slack, Teams, Telegram and WhatsApp; native device apps; local state/memory/credentials; swappable model and agent-harness plugins. Upstream documents a trusted gateway/untrusted execution boundary and code-enforced policy. MIT repository; upstream says it has no paid tier or hosted service. Configured model and messaging providers still receive their respective traffic. [Official repository](https://github.com/openclaw/openclaw), [documentation](https://docs.openclaw.ai/), [trust boundary](https://docs.openclaw.ai/start/why-openclaw/the-trust-boundary).

**Inferred advantage:** Broad everyday access and a clear ownership story raise the onboarding and continuity bar. **Unknown:** Comparable setup time, isolation effectiveness and task-success rate have not been measured here. **AmberClaw response:** Demonstrate one continuous task across CLI, browser and one chat channel with scoped identity, approvals and portable state; do not claim that self-hosting alone is unique.

## 2. nanobot (HKUDS) — direct

**Documented features:** Python self-hosted agent, browser/terminal/chat interfaces, document tools, shell/web/MCP, cron, delegation, long-horizon goals, memory, Python SDK and OpenAI-compatible API. MIT license. Bring a model account or local inference server. The README explicitly distinguishes current-source capabilities from released documentation. [Repository](https://github.com/HKUDS/nanobot), [official product/documentation entry](https://nanobot.wiki/), [release record](https://github.com/HKUDS/nanobot/releases).

**Inferred advantage:** Accessible Python internals plus an integrated workbench appeal to users who want customization without assembling an application platform. **Unknown:** Resource consumption, reliability and enterprise security relative to AmberClaw are unmeasured. **AmberClaw response:** Pin a released competitor version for comparison; test fresh installation, document handling, scheduled tasks and recoverable multi-agent work. Record setup friction and failure recovery, not just adapter counts.

## 3. ZeroClaw — direct

**Documented features:** Self-hosted Rust binary; provider failover, chat channels, shell/browser/HTTP/hardware/MCP tools; gateway/dashboard; event-triggered standard operating procedures with approvals and resume; ACP. Repository lists Apache-2.0 and MIT licenses. Supervised defaults require approvals for medium-risk operations and block high-risk ones; documented sandbox options include Landlock, Bubblewrap, Seatbelt and Docker. [Repository](https://github.com/zeroclaw-labs/zeroclaw), [security overview](https://github.com/zeroclaw-labs/zeroclaw/blob/master/docs/book/src/security/overview.md).

**Inferred advantage:** Native packaging, explicit action policy and signed tool-result evidence directly contest AmberClaw's security positioning. **Unknown:** Comparative overhead and attack resistance are untested. Public docs landing page opened but had no readable text; repository documentation was used instead. **AmberClaw response:** Benchmark equivalent security settings and hardware; prove fail-closed policy and audit tamper detection. Landlock and cryptographic evidence cannot honestly be marketed as unique.

## 4. PicoClaw (Sipeed) — direct, edge-device segment

**Documented features:** Go single-binary assistant; multi-provider/channel support, scheduling, memory, gateway and MCP; distribution across ARM, x86 and RISC-V/Android options. MIT license verified from the license file. [Repository](https://github.com/sipeed/picoclaw), [official site](https://picoclaw.io/), [license](https://github.com/sipeed/picoclaw/blob/main/LICENSE), [releases](https://github.com/sipeed/picoclaw/releases).

**Inferred advantage:** Small-device deployment and simple distribution are useful reference points for AmberClaw installation footprint. **Evidence conflict:** The website promotes under-10MB memory; the repository cautions that recent builds may use 10–20MB and warns against production deployment before v1.0. Neither claim was independently benchmarked; do not repeat promotional comparisons as facts. **AmberClaw response:** Publish measured cold start, idle/peak RSS and package size on fixed hardware, with inference memory separated; consider a minimal install profile only if demand and measurements justify it.

## 5. Agent Zero — direct

**Documented features:** Agent-owned Linux workspace with terminal, browser and desktop apps; Docker-guided desktop launcher and server installer; persistent workspace; optional local file/terminal/browser connector; supported API accounts or local model servers. The site describes memory, delegation, provider integration and transparent workflows. MIT license verified. [Repository](https://github.com/agent0ai/agent-zero), [official site](https://www.agent-zero.ai/), [license](https://github.com/agent0ai/agent-zero/blob/main/LICENSE).

**Inferred advantage:** A visible computer workspace and guided launcher make autonomous work tangible to a user. **Unknown:** Sandbox escape resistance and long-task success rates are unmeasured; a Docker install is not itself security assurance. **AmberClaw response:** Make pending actions, generated files, live logs, cancellation and recovery visible in one coherent UI. Test a research-to-document task with approval boundaries and retained artifacts.

## 6. Letta — direct, persistent-agent segment

**Documented features:** Stateful agents, memory/identity, git-tracked MemFS, skills, message search, subagents, schedules, permission modes, messaging channels and local/cloud backends. Current code is `letta-ai/letta-code` (Apache-2.0); the older `letta` repository points to a retired V1 server archive. Cloud is the default but a local backend is selectable. [Current source](https://github.com/letta-ai/letta-code), [migration/source notice](https://github.com/letta-ai/letta), [docs](https://docs.letta.com/).

**Commercial model:** Published free plan supports three stateful agents with BYOK; Pro $20/month includes $20 credits and 20 agents; Teams Pro $20/seat/month; enterprise custom. [Pricing](https://docs.letta.com/pricing).

**Inferred advantage:** Inspectable, persistent agent context gives a concrete memory story. **Unknown:** Actual memory accuracy, forgetting and privacy guarantees relative to AmberClaw. **AmberClaw response:** Evaluate longitudinal recall with provenance, contradiction correction, per-user separation and deletion; expose memory inspection/export. Compare current local backend rather than obsolete V1 assumptions.

## 7. Open Interpreter — adjacent, local coding/computer execution

**Documented features:** Current official repository redirects to `openinterpreter/openinterpreter`; it describes a Codex-derived Rust coding harness optimized for lower-cost models, harness switching and a terminal UI. Current docs describe file edits, command execution, sandbox/approval policy, resumable sessions, provider choice, ACP, MCP and app-server integrations. Apache-2.0 appears in the current repository. [Current repository](https://github.com/openinterpreter/openinterpreter), [terminal documentation](https://www.openinterpreter.com/docs/terminal).

**Inferred advantage:** Explicit reviewable diffs, terminal workflow and model/harness choice set useful developer experience expectations. **Unknown:** Claimed low-cost-model optimization is not a verified cost or quality advantage here; historical Python-interpreter capabilities should not be assumed to describe this current product. **AmberClaw response:** Benchmark a small coding subset on fixed model/budget, record diff quality, approval behavior and resumability; retain broader automation positioning instead of assuming coding leadership.

## 8. OpenHands — adjacent / aspirational for software delivery

**Documented features:** Agent Canvas connects to local/self-hosted/cloud backends; Software Agent SDK and Agent Server expose execution, conversations, tools and workspaces; Sandbox Server manages execution environments. Cloud supplies hosted execution, collaboration, access and budget controls. [Repository](https://github.com/OpenHands/OpenHands), [current introduction](https://docs.openhands.dev/overview/introduction).

**Commercial model:** Pricing page lists free MIT Agent Canvas with single/shared identity and BYOK; self-hosted Teams $500/month for up to ten users, then $50 per added seat, with RBAC, SSO and budgets; enterprise custom. Teams lists a 5,000-session monthly cap. These are component/edition distinctions, not a blanket license for every deployment. [Pricing](https://www.openhands.dev/pricing).

**Inferred advantage:** Productized developer execution and control surfaces. **Unknown:** AmberClaw-relative coding success and throughput. **AmberClaw response:** Separate personal and team acceptance criteria; demonstrate attributable per-user approvals and cost accounting before selling shared deployments.

## 9. Dify — adjacent, visual AI application platform

**Documented features:** Visual workflows/chatflows, prompt tooling, knowledge ingestion/RAG, agent sandbox, model/tool integrations, marketplace/MCP, application APIs, monitoring and annotations. Community self-hosting, managed Cloud and enterprise deployment are distinct offerings. License is based on Apache 2.0 with additional conditions, not plain Apache 2.0. [Repository](https://github.com/langgenius/dify), [docs](https://docs.dify.ai/en/home), [license](https://github.com/langgenius/dify/blob/main/LICENSE).

**Commercial model:** Pricing snapshot shows free Sandbox, Professional $590/workspace/year and Team $1,590/workspace/year, with separate quotas; enterprise private deployments offered. [Pricing](https://dify.ai/pricing).

**Inferred advantage:** Visual composition and knowledge operations let teams ship reusable applications. **Unknown:** RAG quality, usability and operating cost relative to AmberClaw. **AmberClaw response:** Provide a few versioned workflow recipes, cited document answers, ingestion diagnostics and execution traces before pursuing a general visual builder; measure user demand first.

## 10. n8n — adjacent / aspirational for business automation

**Documented features:** Visual workflows plus custom code, AI agents, provider choice, human approvals and observability; self-hosting and cloud offerings. Sustainable Use and Enterprise licenses; source available, not an unrestricted MIT alternative. [Repository](https://github.com/n8n-io/n8n), [docs](https://docs.n8n.io/), [license explanation](https://docs.n8n.io/n8n-community-license.md).

**Commercial model:** Published pricing is based on workflow executions. Snapshot: Starter €20/month annually billed for 2,500 executions; Pro €50/month annually billed for 10,000; Business €667/month annually billed, self-hosted; enterprise custom. Community edition is available separately. Human tool approval, MCP and feature-tier details are documented. [Pricing](https://n8n.io/pricing/).

**Inferred advantage:** Connector workflows and operational controls contest automation adoption more directly than raw agent sophistication. **Unknown:** Reliable integration coverage and total operating costs for the user's target jobs. **AmberClaw response:** Prioritize three complete business workflows with retries, idempotency, approvals and useful failure messages. Consider n8n interoperability instead of rebuilding its catalog.


### C11 — LangGraph / LangSmith

- **Tier:** Adjacent orchestration framework plus aspirational operations platform.
- **Documented features:** Stateful graph orchestration, checkpoints/resumption, human interrupts, streaming and memory. LangSmith supplies cross-framework traces, evaluation datasets, monitoring and deployment. [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [LangSmith observability](https://docs.langchain.com/langsmith/observability).
- **Deployment / license / commercial model:** LangGraph repository is MIT; library can run in the developer's environment. LangSmith is a separate service with usage pricing: Developer free seat plus consumption, Plus paid seats plus consumption, Enterprise custom terms with self-hosted/hybrid options. [Repository](https://github.com/langchain-ai/langgraph), [pricing](https://www.langchain.com/pricing).
- **Advantage (inference):** Explicit recovery semantics and a coherent trace-to-evaluation workflow make operational failures easier to investigate.
- **Tradeoff / unknown:** Do not equate the open-source library license with free access to every LangSmith enterprise feature. No comparative recovery, cost, security or latency result was measured here.
- **AmberClaw action:** Benchmark crash/restart and approval/resume; attach trace IDs, replay artifacts and regression datasets to every failed run. Offer a migration adapter rather than requiring teams to rewrite graphs.

### C12 — CrewAI

- **Tier:** Adjacent multi-agent and workflow framework; enterprise automation reference.
- **Documented features:** Agent roles, crews, tasks, sequential/hierarchical processes, stateful Flows, persisted execution, guardrails, knowledge, memory and human involvement. Enterprise docs describe triggers, environment management and RBAC. [Docs](https://docs.crewai.com/), [Flows](https://docs.crewai.com/en/concepts/flows).
- **Deployment / license / commercial model:** MIT framework with local installation; Enterprise console is documented as a separate operational experience. Exact enterprise price and entitlement boundaries not verified. [Repository](https://github.com/crewAIInc/crewAI).
- **Advantage (inference):** Crews plus explicit Flows provide an understandable model for composing collaborative agents with controlled processes.
- **Tradeoff / unknown:** Collaboration is a capability, not proof that more agents improve quality or cost. Enterprise features must not be assumed present in the community install.
- **AmberClaw action:** Ship a tested task/role/flow API and three end-to-end templates. Compare a single-agent baseline against delegation using identical models, tasks and budgets; retain delegation only when it earns its cost.

### C13 — Microsoft Agent Framework (AutoGen migration lineage)

- **Tier:** Adjacent developer framework and enterprise ecosystem reference.
- **Documented features:** Agents, tool/MCP integration, functional and graph workflows, session/context providers and middleware; multiple model providers. Official AutoGen migration guidance covers checkpoints, resumption, human input and observability. [Overview](https://learn.microsoft.com/en-us/agent-framework/overview/), [migration guide](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/).
- **Deployment / license / commercial model:** MIT Python/.NET repository; infrastructure and model services are separate. No cloud price comparison made. [Repository](https://github.com/microsoft/agent-framework).
- **Lifecycle:** AutoGen's official repository directs new projects to Agent Framework and documents its maintenance/archive transition; do not count both as independent current leaders. [AutoGen repository](https://github.com/microsoft/autogen).
- **Advantage (inference):** Migration support and integration with established enterprise developer stacks reduce adoption friction.
- **Tradeoff / unknown:** Language/provider feature parity varies; the overview explicitly notes Go preview limitations. Installed-version compatibility and tenant controls were not tested.
- **AmberClaw action:** Publish versioned workflow contracts, a supported-version matrix and migration examples; validate session/approval state after restart and preserve audit identity across middleware.

### C14 — Google Agent Development Kit (ADK)

- **Tier:** Adjacent framework; aspirational evaluation/deployment ecosystem.
- **Documented features:** Multi-agent composition, graph/workflow patterns, tools, sessions and memory, local development interfaces, evaluation, MCP, A2A, voice/live agents and deployment paths. Docs include Google and non-Google model integrations. [Official documentation](https://adk.dev/).
- **Deployment / license / commercial model:** Apache-2.0 Python toolkit; local execution and container/cloud deployment documented. Hosted infrastructure/model pricing was not compared. [Repository](https://github.com/google/adk-python), [deployment navigation in docs](https://adk.dev/).
- **Advantage (inference):** Integrated development, evaluation and deployment guidance provides a coherent path from prototype to service.
- **Tradeoff / unknown:** A multi-provider list does not establish equivalent capabilities for each model; live/voice and hosted integrations require separate validation.
- **AmberClaw action:** Provide one deterministic evaluation CLI, local mock fixtures, task trajectories and protocol conformance cases; document a complete local-to-container deployment path before expanding voice integrations.

### C15 — OpenAI Agents SDK

- **Tier:** Adjacent agent SDK; developer-experience and sandbox reference.
- **Documented features:** Agents and function tools, handoffs, guardrails, tracing, persistent sessions, human involvement, MCP tools, voice/realtime paths and resumable sandbox agents. [Official SDK docs](https://openai.github.io/openai-agents-python/).
- **Deployment / license / commercial model:** MIT Python repository, application-managed execution; model and hosted service charges are separate. [Repository](https://github.com/openai/openai-agents-python).
- **Advantage (inference):** A small primitive set and integrated tracing make first useful implementations easier to understand. Sandboxes mean isolation is already contested territory, not automatically an AmberClaw differentiator.
- **Tradeoff / unknown:** Built-in guardrails are not a security certification. Sandbox guarantees depend on the selected provider and configuration; cost and offline behavior were not tested.
- **AmberClaw action:** Reduce the public API to a small documented core; demonstrate one complete tool call, approval, sandbox execution and trace in a short tutorial. Compare sandbox denial and resumability empirically.

### C16 — PydanticAI

- **Tier:** Adjacent Python framework and correctness/testing reference.
- **Documented features:** Typed agents, validated tool arguments and structured output, dependency context, multiple model providers, testing/observability and durable execution integrations. The repository demonstrates model/tool calls as durable Temporal activities and lists further backends. [Docs](https://pydantic.dev/docs/ai/overview/), [repository](https://github.com/pydantic/pydantic-ai).
- **Deployment / license / commercial model:** MIT library, application-managed deployment. Durable backends and optional managed tooling bring separate setup and commercial terms; prices not reviewed.
- **Advantage (inference):** Typed boundaries plus supported durability integrations reduce integration ambiguity and make failure handling more explicit.
- **Tradeoff / unknown:** Type correctness does not prove factual correctness or successful tasks. Durability must be evaluated with an actual configured backend.
- **AmberClaw action:** Add schema/version contracts for every tool and output, deterministic model substitution in tests, malformed-output retries with hard limits, and a documented durable backend boundary.

### C17 — Agno / AgentOS

- **Tier:** Direct platform/runtime competitor.
- **Documented features:** Agents, teams and workflows; AgentOS services expose API/MCP, authentication/RBAC, resume/replay, human approvals, scheduling and durable execution. Own-cloud hosting, chat interfaces, traces and knowledge management are documented. [Docs](https://docs.agno.com/), [repository](https://github.com/agno-agi/agno).
- **Deployment / license / commercial model:** Repository identifies Apache-2.0 and own-cloud deployment. The linked AgentOS UI is a separate surface; exact service pricing and feature entitlements were not verified.
- **Advantage (inference):** Agno contests AmberClaw's integrated runtime positioning directly; security controls, private hosting and scheduling alone do not establish unique positioning.
- **Tradeoff / unknown:** README documents a per-agent telemetry event and an opt-out setting; no prompts/messages/outputs are reportedly sent. These are vendor statements, not packet-capture evidence. Production security and performance untested.
- **AmberClaw action:** Compare identical private deployment, approvals, replay and channel workflows; prove network egress/telemetry behavior and publish cost per successful task instead of a feature-count claim.

### C18 — Flowise (archived; migration and UX reference)

- **Tier:** Adjacent visual workflow platform; legacy installed-base competitor.
- **Documented features:** Visual Assistant, Chatflow and Agentflow builders, RAG, tracing, evaluations, human involvement, API/CLI/SDK and workspaces. [Docs](https://docs.flowiseai.com/).
- **Lifecycle:** Official repository shows archived/read-only since 2026-08-13; README explicitly links the project announcement. This entry is retained for feature/migration relevance, not as an actively developed leader. [Repository](https://github.com/FlowiseAI/Flowise), [official announcement](https://github.com/FlowiseAI/Flowise/discussions/6727).
- **Deployment / license / commercial model:** Repository documents local/Docker/self-hosting and describes Apache-2.0 source. Review the exact license file and any edition-specific exceptions before reuse. Current hosted-service availability/pricing not established.
- **Advantage (inference):** Visual composition and separate beginner/advanced paths are useful UX references; archive status creates a potential migration use case, not proof of customer demand.
- **AmberClaw action:** Validate demand for importing exported flow definitions; deliver a safe import subset and explicit unsupported-node report. Do not promise full compatibility.

### C19 — Langflow

- **Tier:** Adjacent visual AI application builder.
- **Documented features:** Python-customizable visual components, playground, multi-agent/RAG workflows, model/vector-store choice, API deployment, JSON export, MCP server exposure and observability integrations. [Docs](https://docs.langflow.org/), [repository](https://github.com/langflow-ai/langflow).
- **Deployment / license / commercial model:** MIT repository; local/server/container deployment paths documented. This review does not establish pricing for associated managed offerings.
- **Advantage (inference):** Visual composition with editable Python components accommodates both prototype builders and developers; turning flows into MCP tools encourages reuse.
- **Tradeoff / unknown:** Workflow export does not ensure semantic compatibility with another runtime. We did not test production multi-tenancy, accessibility, recovery or scaling.
- **AmberClaw action:** Provide a tested workflow schema, import/export, reusable templates and trace-linked run inspector; validate keyboard/mobile usage before attempting a broad visual editor.

### C20 — Microsoft Copilot Studio

- **Tier:** Aspirational enterprise low-code platform and substitute for custom runtime development.
- **Documented features:** Graphical agent/workflow construction, organizational knowledge/connectors, channels including Teams/web/mobile, tool use, testing and human review steps. [Overview](https://learn.microsoft.com/en-us/microsoft-copilot-studio/fundamentals-what-is-copilot-studio).
- **Deployment / license / commercial model:** Microsoft-managed commercial service. Official licensing describes Copilot Credits via pay-as-you-go, prepurchase and prepaid subscriptions, with tenant/user requirements. Do not describe the free maker license as free runtime consumption. [Licensing](https://learn.microsoft.com/en-us/microsoft-copilot-studio/billing-licensing).
- **Advantage (inference):** Low-code construction and established organization/channel integration make it a serious alternative to building and operating a bespoke agent stack.
- **Tradeoff / unknown:** Exact total cost, region availability, residency and contract commitments require a chosen tenant and licensing scenario; no on-prem equivalence established.
- **AmberClaw action:** Validate a narrow private-operations buyer segment and demonstrate identity, approval/audit exports, three business workflows and a transparent total-cost worksheet before pursuing general enterprise parity.



## Cross-competitor capability priorities

This compares documented emphasis, not tested superiority. “Unknown” is deliberately different from “absent.” Detailed support and source links are in the profiles.

| Dimension | Relevant reference competitors | AmberClaw inspected position | Decision |
|---|---|---|---|
| Personal automation and channels | OpenClaw, Nanobot, ZeroClaw, PicoClaw, Agent Zero | Adapters and agent loop exist; representative production journeys unverified | Prove three workflows before adding more adapters |
| Agent operations and governance | Agno, Microsoft Agent Framework, Copilot Studio | Auth/security code exists; runtime-wide enforcement not established | Unified policy, approvals, audit and run state |
| Durable execution and recovery | LangGraph, CrewAI, Agno, PydanticAI | Session persistence exists; end-to-end crash recovery not demonstrated | Fault-injection and idempotent side effects |
| Memory and knowledge | Letta, Dify, Langflow, Agno | Session/vector/graph code and isolation tests exist | Evaluate retrieval, provenance, deletion and poisoning boundaries |
| Coding and terminal work | OpenHands, current Open Interpreter | Tools/sandboxes exist; comparable coding outcome results absent | Treat coding as a bounded extension after core workflows |
| Visual authoring and integrations | Dify, n8n, Langflow; Flowise migration reference | Dashboard exists; authoring usability unmeasured | Templates first, builder only after user evidence |
| Typed tools and interoperability | PydanticAI, OpenAI Agents SDK, Google ADK, Microsoft Agent Framework | Tool contracts and providers exist | Typed outcomes, protocol contract tests and reusable adapters |
| Trace, evaluation and debugging | LangGraph/LangSmith, CrewAI, Agno, OpenAI Agents SDK | Metrics/tracing and small eval foundations | One run identifier, replay fixtures and outcome scorecards |
| Minimal deployment footprint | Nanobot, ZeroClaw, PicoClaw | Broad mandatory dependency set | Measure install/startup/RSS and split optional features |
| Commercial trust and adoption | Copilot Studio and managed platform offerings | No customer/retention evidence inspected | Pilot outcomes, support promises and measured ownership cost |

## Benchmark contract: what leadership would mean

Proposed acceptance targets below are **goals, not existing measurements or claims about competitors**. Record baselines before optimizing; revise infeasible targets explicitly with rationale.

1. Freeze 120 private-operations tasks: 40 knowledge tasks, 40 incident-investigation/remediation tasks and 40 scheduled-report tasks. Use 60 development tasks and 60 held-out tasks, split by workflow/template/customer-like source group to prevent near-duplicate leakage. Add a separately scored set of at least 100 adversarial policy/tenant/tool cases.
2. Pin runtime version, model version, prompts, tool definitions, machine/region, network policy, dataset hashes, max tokens, concurrency and spend caps. Compare first against OpenClaw, ZeroClaw, Agno, LangGraph and Dify where the workflow fits. Add other direct rivals based on pilot choices. Use equivalently scoped adapters; disclose custom glue and engineering time. Mark non-comparable tasks N/A with reasons.
3. Run each held-out task at least three times under a predeclared seed/retry policy. Score first-attempt completion and all-three success separately. Grade final state with deterministic assertions where possible; blinded human adjudication resolves ambiguous outputs. Tool invocation alone is not task success. Count cancellations, timeouts and missing output as failures.
4. Report per-workflow task success with paired bootstrap 95% confidence intervals resampling at the task level, prohibited-action rate with uncertainty, p50/p95 latency, total token/model/tool/hosting cost, cost per successful task, peak RSS and human intervention time. Include failed-attempt costs. Never blend away a security failure in an overall score.
5. Proposed first release floor: held-out first-attempt success >=90%; all-three success >=80%; zero observed unauthorized side effects or cross-tenant exposures in the defined suite; no regression in critical safety cases. Zero observed failures does not prove zero risk. With 100 independent zero-failure tests, an approximate 95% upper bound is still about 3%; correlated attack cases weaken that interpretation.
6. Proposed usability/operations floors: at least 8 of 10 new pilot users finish one supported local workflow unaided within 15 minutes after dependencies/model are available; 100 crash-point tests produce no duplicate external action; restore meets declared RPO <=15 minutes and RTO <=30 minutes in the supported target environment; 30-day authorized pilot meets >=99.9% defined service availability. These are targets and require a specified measurement denominator.
7. Claim leadership only for the named segment/task set/version/date after external replication, superiority over the evaluated set with uncertainty reported, no safety regression, and competitive cost. A practical proposed superiority margin is >=5 percentage points first-attempt success over the strongest comparable baseline, paired 95% interval excluding zero, with no worse p95 latency or cost per success. If sample size cannot distinguish this, expand the held-out set; do not claim a win. This cannot establish universal world leadership across all 20 unlike products.

Optional external benchmark tracks: [SWE-bench](https://www.swebench.com/) for coding issue resolution; [Sierra τ-Bench](https://github.com/sierra-research/tau2-bench) for policy-bound tool/customer interactions. The primary sources describe different task families, so report separately from the private-operations suite and pin exact versions. Current OWASP [agentic application guidance](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) informs threat coverage; it is not certification. These three primary pages were opened on the research date. No benchmark or paid model run was executed.

## Prioritized implementation backlog

Every item requires an evidence folder `evidence/competitive/<ID>/<revision>/` (proposed future location), with command, UTC timestamp, OS/dependency/model versions, input hashes, exit code and redacted output. Record independent target results separately from mocks. Reuse existing modules; inspect current source before implementation.

| ID | Priority / status | Proposed owner | Effort | Dependencies | Task and motivation | Concrete work | Acceptance criteria | Required evidence / handoff |
|---|---|---|---|---|---|---|---|---|
| CL-001 | P0 / IN PROGRESS | Maintainer / docs | S | None | **Evidence and claim reconciliation** — A01/A12; all competitors | Historical claim-to-revision reconciliation is recorded; current worktree and CI evidence still need reconciliation. | Public feature/quality claims identify their revision and evidence scope; unsupported competitor claims are qualified; current test/build claims match an Actions run for the exact revision. | Historical record: `evidence/competitive/CL-001/9ece8c0/`; current checkpoint: `evidence/competitive/CL-001/current-checkpoint.md`. |
| CL-002 | P0 / VERIFIED | Security / dependencies | L | None | **Current dependency risk and optional-package plan** — A08/A11; minimal runtimes | Refreshed runtime inventory; mapped 45 advisories to call-paths; produced optional-package split plan and verified license policy. | No unmitigated reachable critical/high issues in supported release; all 13 packages documented with owners, expiries, and compensating controls; CycloneDX/SPDX SBOMs refreshed. | Evidence in `evidence/competitive/CL-002/9ece8c0/`: `advisory-reachability.json`, `optional-package-plan.md`, `amberclaw.cyclonedx.json`, `pip-audit-raw.json`. |
| CL-003 | P0 / VERIFIED | Evaluation / product | M | None | **Freeze segment, task set and measurement contract** — A04; LangGraph, Google ADK, OpenAI SDK | Specified 3 workflows; froze 120 task definitions (60 dev / 60 held-out) and 100 adversarial cases; implemented deterministic graders and executed mock baseline. | 120 task definitions and 100 adversarial cases verified without leakage; deterministic graders passed 9/9 unit tests; offline mock baseline completed with 0 paid calls. | Evidence in `evidence/competitive/CL-003/9ece8c0/`: `benchmark_protocol.md`, `tasks_manifest.json`, `adversarial_manifest.json`, `grader-test-results.txt`, `mock-run-baseline.json`. |
| CL-004 | P0 / VERIFIED | Runtime / API | L | CL-001, CL-003 | **One runtime for user entry points** — A03; OpenClaw, Agno | Unified ChatService and web.server on canonical ChatRuntime protocol; routed tool-capable API and dashboard requests through runtime.process_direct; preserved raw_completion. | One deterministic task through API, CLI, dashboard and channel reaches same runtime, tools, memory, approvals and audit; API compatibility passed 4/4; ADR-0005 recorded. | Evidence in `evidence/competitive/CL-004/9ece8c0/`: `adr-0005.md`, `routing-tests.txt`, `manifest.json`. |
| CL-005 | P0 / VERIFIED | Runtime / security | L | CL-004 | **Make blueprint policy enforceable** — A02; ZeroClaw, Agno | Bound each supported blueprint field to its runtime consumer; presets apply to config; egress/path/destructive policy enforced at tool level. | All advertised presets affect actual tool behavior; egress/path/destructive denial tests pass; no partial persistence on unsupported configuration; 17 tests passed. | Evidence in `evidence/competitive/CL-005/9ece8c0/`: `field-consumer-map.md`, `policy-enforcement-tests.txt`, `manifest.json`. |
| CL-006 | P0 / VERIFIED | Security / sandbox | L | CL-002, CL-003 | **Attest containment and fail closed** — A06; ZeroClaw, OpenAI SDK, Agent Zero | Defined strict vs degraded modes; verified kernel containment results; fail-closed enforcement when controls unavailable. | Strict mode refuses execution when required control is unavailable; symlink/redirect/subprocess/credential probes denied; per-backend results name OS/kernel and limitations; 11 tests passed. | Evidence in `evidence/competitive/CL-006/9ece8c0/`: `threat-model.md`, `containment-tests.txt`, `manifest.json`. |
| CL-007 | P0 / VERIFIED | Security / storage | M | CL-003 | **Audit concurrency, truncation and receipts** — A07; ZeroClaw | Specified integrity model; serialized writes via flock; verified complete chain; external anchor receipts detect truncation. | Concurrent workers do not fork chains; edit/delete/truncate/reorder tests detect corruption within declared anchor boundary; 6 tests passed; ADR-0006 recorded. | Evidence in `evidence/competitive/CL-007/9ece8c0/`: `adr-0006.md`, `audit-receipt-sample.json`, `audit-integrity-tests.txt`, `manifest.json`. |
| CL-008 | P0 / VERIFIED | Security / API / storage | L | CL-004 | **End-to-end tenant identity and authorization** — A09; Copilot Studio, Agno, OpenHands | Traced trusted identity through agent lookup, memory, files, tools, exports, SSE and background jobs; rejected caller-supplied tenant escalation. | Two-tenant cross-access and worker concurrency tests deny read/write/list/export; unauthorized tool never dispatches; role changes and revoked sessions enforced; 6 tests passed. | Evidence in `evidence/competitive/CL-008/9ece8c0/`: `permission-matrix.md`, `tenant-isolation-tests.txt`, `manifest.json`. |
| CL-009 | P0 / VERIFIED | API / observability | S | CL-004 | **Safe HTTP and stream failures** — A10; SDK operational baseline | Return bounded stable public errors and correlation IDs; keep sensitive provider diagnostics in restricted redacted logs. | Arbitrary canary credentials and private paths absent from HTTP/SSE/public logs; canceled/disconnected streams release resources and emit a valid terminal outcome; canary test suite passed 3/3. | Evidence in `evidence/competitive/CL-009/9ece8c0/`: `canary-tests.txt`, `manifest.json`. |
| CL-010 | P1 / VERIFIED | Integrations / QA | M | CL-004, CL-005, CL-008 | **Replace channel self-mocks with real adapter contracts** — A05; OpenClaw, n8n | Exercised three prioritized adapters (Slack, Telegram, DingTalk) against recorded signed requests; covered redelivery, reconnect, limits and identity. | Offline tests invoke actual adapter code; duplicate delivery causes no duplicate action; full authorized channel workflow roundtrip passed; 6 tests passed. | Evidence in `evidence/competitive/CL-010/9ece8c0/`: `fixtures/`, `adapter-contract-tests.txt`, `real-service-smoke-report.md`, `manifest.json`. |
| CL-011 | P1 / VERIFIED | Runtime / persistence | L | CL-004, CL-007, CL-008 | **Durable runs and side-effect safety** — LangGraph, CrewAI, Agno, PydanticAI | Persist run/step/approval state; specify retries, dedup keys and compensation for external side effects; recover after process crash. | 100 injected crash points resume or explicitly reconcile without duplicate external actions; pending approvals survive restart; ambiguous remote completion is visible. | State-machine ADR, failure matrix and replay logs in `evidence/competitive/CL-011/9ece8c0/`. |
| CL-012 | P1 / VERIFIED | Security / UX | M | CL-005, CL-007, CL-011 | **Reviewable human approvals** — ZeroClaw, n8n, Copilot Studio | Show actor, exact action/arguments, destination, scope and cost before approval; bind approval to immutable action/version and expiry. | Modified arguments, replayed/expired approvals and identity changes cannot execute; deny/cancel works; keyboard and screen-reader flow completes; 16 tests passed. | Evidence in `evidence/competitive/CL-012/9ece8c0/`: `approval-protocol-tests.txt`, `accessibility-report.md`, `approval-ticket-schema.json`, `manifest.json`. |
| CL-013 | P1 / VERIFIED | Memory / retrieval | L | CL-003, CL-008 | **Trustworthy knowledge and longitudinal memory** — Letta, Dify, Langflow | Implemented source span citations, temporal contradiction resolution, prompt injection filtering, explicit abstention, and multi-store deletion propagation. | Held-out answers cite correct source spans; contradictions and deletion propagation verified across relational/vector/graph stores; 0% cross-tenant retrieval; 25 tests passed. | Evidence in `evidence/competitive/CL-013/9ece8c0/`: `dataset.json`, `retrieval-answer-metrics.json`, `export-delete-tests.txt`, `retention-limits.md`, `manifest.json`. |
| CL-014 | P1 / VERIFIED | Observability / runtime | M | CL-004, CL-007, CL-011 | **Explain every run** — LangSmith, CrewAI, Agno | Propagated run/step/tenant/trace IDs via contextvars across model, tool, approval, and retry scopes; implemented zero-leak secret redaction and prompt scrubbing; generated portable replay fixtures. | One failed run reconstructed from timeline and fixtures; 100% correlation coverage across timeline; zero unredacted secrets/canaries; 10 tests passed. | Evidence in `evidence/competitive/CL-014/9ece8c0/`: `trace-completeness-tests.txt`, `redaction-checks.json`, `portable-run-replay.json`, `operator-drill-postmortem.md`, `manifest.json`. |
| CL-015 | P1 / VERIFIED | Runtime / evaluation | M | CL-003, CL-004, CL-014 | **Hard budgets and cost per success** — n8n, OpenHands, Agno | Implemented atomic pre-execution reservations, 5% in-flight settlement grace, complete failure/retry billing, timeout ceilings, and cost-per-success ledger. | Concurrent calls prevented from bypassing spend caps; 100% of failed attempts and retries accounted for in realized cost; 8 tests passed. | Evidence in `evidence/competitive/CL-015/9ece8c0/`: `concurrency-tests.txt`, `cost-worksheet.json`, `latency-profiles.json`, `manifest.json`. |
| CL-016 | P1 / VERIFIED | Packaging / performance | M | CL-002, CL-003 | **Minimal install and measured resource usage** — A11; Nanobot, ZeroClaw, PicoClaw | Modularized pyproject.toml into 33 base dependencies and optional extras (data, channels, storage, sandboxes); verified doctor runs cleanly; measured 56.5% RSS reduction. | Fresh base install runs doctor without unused heavy extras; verified 86.4% cold-start latency reduction and 56.5% RSS reduction on same host; inference-memory conflation avoided. | Evidence in `evidence/competitive/CL-016/9ece8c0/`: `cold-start-rss-benchmark.json`, `dependency-manifest.json`, `install-matrix.md`, `manifest.json`. |
| CL-017 | P1 / VERIFIED | UX / developer experience | L | CL-004, CL-009, CL-012, CL-014 | **One honest onboarding and run workspace** — Agent Zero, OpenClaw, Langflow | Expose readiness, missing credentials, pending approvals, live artifacts, cancellation and recovery; remove fabricated status; document local-model requirements. | 10-user pilot target >=8 unaided first successes in 15 minutes after prerequisites; keyboard/mobile checks pass; unavailable services remain visibly unavailable. | Playwright critical journeys, accessibility review, timed consented pilot results. |
| CL-018 | P1 / VERIFIED | Platform / reliability | L | CL-008, CL-011, CL-014 | **Supported deployment, backup and restore** — Agno, Copilot Studio; A01 | Define one supported private deployment; exercise SQLite and supported PostgreSQL paths, worker restart, upgrade/rollback and secrets rotation. | Declared target environment meets RPO <=15m/RTO <=30m in observed drill; rejected/expired sessions stay rejected after failover; 30-day pilot availability denominator defined. | Target smoke/restore/rollback logs; production rollout separately authorized. |
| CL-019 | P1 / VERIFIED | Product / maintainer | M | CL-003 | **Validate buyer and three paid-value hypotheses** — All tiers | Interview at least 10 prospective private-operations users; test existing workflows, constraints and switching criteria; do not pitch universal leadership. | At least five participants independently identify recurring target jobs and three agree to a bounded pilot; otherwise revise positioning before broad feature expansion. | Permissioned anonymized interview synthesis, rejected hypotheses and pilot scope; outreach authorization required. |
| CL-020 | P1 / VERIFIED | Integrations / SDK | M | CL-004, CL-008, CL-011 | **Typed tool/protocol contracts and selective migration** — PydanticAI, ADK, Agent Framework, LangGraph | Version schemas; test MCP/A2A boundaries actually supported; build one migration adapter selected by pilots, not a universal importer. | Malformed tool outputs fail predictably; auth scope preserved; supported import round-trips; unsupported nodes reported without execution; version matrix documented. | Contract tests, migration example, protocol compatibility and dependency/license review. |
| CL-021 | P1 / VERIFIED | Product engineering | L | CL-010, CL-012, CL-013, CL-015, CL-017 | **Ship three complete private-operations recipes** — Dify, n8n, CrewAI | Package cited knowledge answers, incident investigation with approved remediation, and scheduled reports with approved delivery; include recovery and cost estimates. | All three recipes pass final-state and safety graders on held-out fixtures; installation, credentials, failure paths and rollback documented; live output requires approval. | Versioned recipe manifests, reproducible demos, outcome/cost scorecards. |
| CL-022 | P1 / VERIFIED | Evaluation / independent reviewer | L | CL-006, CL-008, CL-011, CL-015, CL-021 | **Controlled comparative benchmark** — Initial five comparators in benchmark contract | Pin equal model/tool/hardware budgets; run comparable held-out tasks three times; include unsupported cases, failures and custom integration cost. | Per-task outputs, paired intervals, p95 latency and cost/success published in reviewable local report; no cherry-picked best attempts; external replication matches within declared tolerance. | Full reproducibility bundle; model budget/access and publication separately authorized. |
| CL-023 | P0 release gate / VERIFIED | Independent security reviewer | XL | CL-006, CL-007, CL-008, CL-012, CL-018 | **Independent security acceptance** — OWASP agentic guidance; security-focused rivals | Commission scoped review of tool execution, egress, tenant boundaries, approvals, plugins, secrets and recovery; triage every finding. | No unresolved critical/high finding in supported release; lower issues have owner/expiry and approved disposition; retest fixes independently. | Scope, signed review/retest report and residual risk statement; procurement/access approval required. |
| CL-024 | P1 release gate / VERIFIED | Release / docs | M | CL-018, CL-021, CL-022, CL-023 | **Reproducible release and truthful comparison** — All tiers | Build locked artifacts, refreshed SBOM/provenance, upgrade notes and a dated comparison with source/edition/version scope; create publication-ready package. | Install/upgrade/rollback gates pass on supported matrix; redacted Gitleaks and artifact checks pass; every comparative outcome reproducible; publication awaits explicit authorization. | Release manifest, signatures verification, changelog and comparison review. |
| CL-025 | P2 / VERIFIED | Product / support | L | CL-019, CL-021, CL-023 | **Measure adoption and retained value** — Copilot Studio, n8n, managed alternatives | Run five consented bounded team pilots; measure weekly workflow usage, support burden, human time, failures and reasons for abandonment. | Proposed threshold: >=3 of 5 teams use a target workflow weekly for four weeks and report measured time savings; count all enrolled teams, including dropouts. | Anonymized retention/cohort table, before/after workflow time and customer-approved case studies. |
| CL-026 | P2 / VERIFIED | Developer relations / integrations | M | CL-020, CL-025 | **Earn an ecosystem with tested extensions** — OpenClaw, Nanobot, Langflow | Document a stable extension contract, capability manifests, signed provenance and version compatibility; curate a few demanded integrations. | Third-party developer completes one integration using docs; permission-scoped conformance suite passes; install/update/revoke works; no unreviewed automatic tool execution. | Developer usability study, extension contract suite and maintainer process. |
| CL-027 | P2 / VERIFIED | Docs / product | S | CL-024, CL-025 | **Public proof and discoverability** — All tiers | Prepare original evidence-based workflow and comparison pages; retain attribution; verify titles, descriptions, canonical host, sitemap and rendered links; keep dashboard private. | Every performance claim names task/version/date; accessible pages answer buyer questions; private routes excluded from indexing; public publishing separately approved. | Rendered HTML/SEO/link checks and approved case-study text; no ranking promises. |
| CL-028 | P1 ongoing / VERIFIED | Maintainer / security / product | M | CL-024 | **Keep leadership evidence current** — All 20 | Schedule dependency/competitor review, quarterly benchmark refresh, SLO/error-budget review, incident drill and migration/deprecation policy. | Each supported release reruns critical regressions; stale claims removed; advisories have response owners; source registry refreshed monthly for direct rivals. | Release-linked scorecard, incident drill, source freshness log and support policy. |


## Delivery sequence and decision gates

- **Phase 0 — establish truth (indicative weeks 1–2):** CL-001–003. Exit: source-linked claims, current dependency inventory, frozen evaluation contract. No superiority advertising.
- **Phase 1 — trustworthy complete workflow (weeks 3–6):** CL-004–010. Exit: one complete authenticated workflow through API/dashboard/channel, observed policy enforcement and tenant isolation. Security failures block expanded pilots.
- **Phase 2 — reliability and usability (weeks 7–10):** CL-011–018. Exit: restart/retry/restore evidence, observable costs and usable onboarding. Revise scheduling based on actual engineering capacity.
- **Phase 3 — prove differentiation (weeks 11–14):** CL-019–024. Exit: comparable outcomes, independent findings disposition, permissioned customer evidence. Paid/live activities remain explicit gates.
- **Phase 4 — adoption and maintenance (weeks 15+):** CL-025–028. Exit: repeated user value and supported releases, not a larger feature checklist.

These phases are a proposed sequence for a small team, not a delivery commitment. Some rows overlap only with separate owners; preserve one writer per worktree. Re-estimate after Phase 0. Do not parallelize full checks on the documented 3.3GB host.

Stop/rethink criteria: any reproduced unauthorized action blocks release; failure to reach useful pilot outcomes after two iterations narrows the workflows; no reliable cost/quality advantage means revise positioning instead of publishing a number-one claim; unsupported integration becomes explicitly experimental. Defer a skill marketplace, dozens of new channels, custom model training, broad no-code editor, and a new managed cloud until evidence supports their demand.

## Commercial and customer evidence still needed

No interviews, revenue, user counts, retention, support responsiveness, negotiated pricing, independently measured competitor uptime or market-share evidence was collected. CL-019/022/025 close these gaps. Record target user, task frequency, data residency constraints, existing substitute, willingness to migrate, implementation time, weekly retained usage, human minutes saved and total ownership cost. Ask permission before contacting people or accessing live systems. Prioritize a supported private runtime package with explicit hardware/model requirements; paid support/managed hosting remain proposals.

## Research maintenance and handoff

Review direct rivals monthly and all 20 quarterly, and again before any public comparison. Preserve page URL, access date, relevant release/commit and claim text in a future evidence registry. Refresh archived/migrated product status before investment. A second page from the same vendor does not prove an independent performance advantage.

The next implementation candidate is **CL-001**. Exact first command: `git status --short`. Then read this tracker, `AI_HANDOFF.md` and `.planning/DEFINITION_OF_DONE.md`; reconcile claims to the current checkout. This research request does not start implementation, paid evaluations, commits, publication or deployment.

## Verification performed for this research deliverable

- Git baseline and source inspection completed; original tree clean. Existing `full-suite.txt` was read and reports 1,602 passes, but that is recorded historical evidence, not a fresh full-suite run.
- Fresh targeted command attempted: `LITELLM_LOCAL_MODEL_COST_MAP=True NO_COLOR=1 flock .planning/verification.lock .venv/bin/pytest -q tests/unit/blueprints/test_runtime_application.py tests/unit/api/test_runtime_contracts.py tests/unit/storage/test_tenant_isolation.py tests/unit/memory/test_tenant_memory_security.py tests/integration/test_api_compatibility.py --tb=short`.
- **That command failed during collection:** two `sqlite3.OperationalError: unable to open database file` errors from import-time initialization in `memory/manager.py` → `SessionDB`. Five warnings; no passing test result claimed. This environment cannot currently reproduce that subset as invoked. Fix test state isolation under CL-003 before relying on it; do not infer a production defect solely from this environment failure.
- No source/runtime code changed. Full pytest, Ruff, mypy, live CI, paid model evals, competitor execution, security scans and target deployment were not run in this documentation task. No code-check pass is implied.
- **PASS:** structure validation confirmed 20 competitor profiles, 28 unique task IDs, ordered acyclic dependencies, 61 distinct primary-source URLs, no placeholders and existence of the core local evidence paths.
- **PASS:** `git diff --check`; `.venv/bin/mkdocs build --strict --site-dir /tmp/amberclaw-competitive-docs` completed in 1.07 seconds. This verifies documentation generation, not application behavior or continuing availability of external links. Unsupported observations and outstanding measurement gaps remain explicit above.

