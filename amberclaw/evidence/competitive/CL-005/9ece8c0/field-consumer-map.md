# Blueprint Field to Runtime Consumer Mapping (CL-005 / Observation A02)

| Blueprint Field | Canonical Config Path | Runtime Consumer(s) | Enforcement Mechanism | Failure / Denial Behavior |
|---|---|---|---|---|
| `agent.model_name` | `Config.agents.defaults.model` | `AgentLoop`, `LLMRouter` | Primary provider model resolution | Falls back to declared `fallback_models` or fails with invalid model specification |
| `agent.temperature` | `Config.agents.defaults.temperature` | `AgentLoop`, `LLMRouter` | Model sampling parameter | Bounded to [0.0, 2.0] by Pydantic validator |
| `agent.max_turns` | `Config.agents.defaults.max_tool_iterations` | `AgentLoop._graph` (AgentGraph) | Graph recursion / turn loop limit | `RunawayLoopGuard` terminates execution when iteration limit is reached |
| `agent.system_prompt` | `Config.agents.defaults.system_prompt` | `ContextBuilder.build_system_prompt` | Custom directive injected into system messages | System prompt prepended to context window for model guidance |
| `agent.memory_nudge_enabled` | `Config.agents.defaults.memory_nudge_enabled` | `AgentLoop._apply_memory_nudges` | `MemoryNudgeSystem` conditional trigger | When disabled (`False`), background memory nudges are bypassed entirely |
| `security.sandbox_type` | `Config.security.sandbox_type` | `CodeSandbox`, `DockerTerminalBackend` | Container/isolation environment selector (`docker`, `local`, `wasm`, `modal`) | Unknown backend rejected atomically by `BlueprintApplier` without saving |
| `security.allow_network_egress` | `Config.security.allow_network_egress` | `WebSearchTool`, `WebFetchTool`, `BrowserActionTool`, `ExecTool` | Tool pre-execution policy checks | Direct rejection with `"Error: Network egress is disabled by security policy"` |
| `security.restricted_paths` | `Config.security.restricted_paths` | `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `ListDirTool`, `ExecTool` | `_resolve_path` and `_guard_command` path ancestry checks | `PermissionError("Access to restricted path '...' is forbidden by security policy")` |
| `security.require_human_approval_for_destructive` | `Config.security.require_human_approval_for_destructive` | `ToolRegistry.execute` -> `ToolApprovalManager` | HITL ticket issuance for `write_file`, `edit_file`, and `exec` | Execution blocked with pending ticket ID until authorized by operator |
| `skills` | `Config.skills` | `ContextBuilder.build_system_prompt` | Included in active skill context | Filtered to installed workspace skills |
| `channels` | `Config.channels.<name>.enabled` | `ChannelManager._init_channels` | Adapter initialization toggles | Unrecognized channel names rejected atomically |
