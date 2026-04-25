# Roadmap: AmberClaw

## Overview

Finalizing the core architecture, improving production reliability, and expanding the terminal-native agent experience through unified tool management and performance optimizations.

## Phases

- [ ] **Phase 1: Critical Fixes & Unification Completion** - Complete legacy cleanup and system health.
- [ ] **Phase 2: Core Architecture Upgrades** - Async concurrency and MCP integration.
- [ ] **Phase 3: Terminal Experience & UI** - Real-time streaming and interactive shell refinements.

## Phase Details

### Phase 1: Critical Fixes & Unification Completion
**Goal**: Finalize unification, fix critical bugs, and implement system health checks.
**Depends on**: Initial project unification (completed).
**Success Criteria**:
  1. `amberclaw doctor` command identifies configuration and dependency issues.
  2. Data operations do not block the main async event loop.
  3. No legacy stubs remain in the core tool registry.
**Plans**: 1 plan

Plans:
- [ ] 01-01: Implementation of `doctor` and async pandas offloading.

### Phase 2: Core Architecture Upgrades
**Goal**: Improve performance through parallel execution and expand capabilities with MCP.
**Depends on**: Phase 1
**Success Criteria**:
  1. Independent tool calls execute concurrently via `asyncio.TaskGroup`.
  2. External MCP servers can be registered and used as tool sources.
**Plans**: 2 plans

Plans:
- [ ] 02-01: Parallel tool execution implementation.
- [ ] 02-02: MCP server integration.

### Phase 3: Terminal Experience & UI
**Goal**: Provide a premium, responsive terminal-native interaction layer.
**Depends on**: Phase 2
**Success Criteria**:
  1. Response tokens stream in real-time using `rich.live`.
  2. Command history and tab-completion work seamlessly in `amberclaw chat`.
**Plans**: 2 plans

Plans:
- [ ] 03-01: Real-time streaming integration.
- [ ] 03-02: Interactive shell enhancements.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Unification | 0/1 | In progress | - |
| 2. Architecture | 0/2 | Not started | - |
| 3. UI/UX | 0/2 | Not started | - |
