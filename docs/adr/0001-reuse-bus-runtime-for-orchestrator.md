# ADR-0001: Reuse the existing bus runtime for the orchestration adapter

**Date:** 2026-11-06
**Status:** accepted
**Deciders:** Local implementation under the authorized STAB-02 tracker task

## Context

The legacy core orchestrator has no current CLI/API callers and references
obsolete configuration, channel constructors, and AgentLoop signatures.
The gateway already constructs AgentLoop and ChannelManager on one MessageBus.
Duplicating that construction in core would create a second configuration and
provider-routing path and violate dependency injection rules.

## Decision

Keep the importable Orchestrator as a lifecycle and legacy-message adapter.
Applications inject existing AgentLoop and ChannelManager instances sharing
one bus. The adapter uses their current run/start_all/stop APIs. The unconfigured
global singleton fails explicitly on start and performs no provider or channel I/O.

## Alternatives considered

- Delete the unused adapter: simpler, but removes an existing import surface.
- Rebuild provider/channel construction inside core: convenient no-argument
  startup, but duplicates the gateway's wiring and can start external services
  implicitly. Rejected in favor of existing runtime interfaces.

## Consequences

Callers must configure dependencies before startup. Legacy messages require
explicit routing identifiers, preventing unknown-user session collisions and
accidental default-channel delivery. Startup failure and shutdown drain owned
tasks. Transport authorization remains the channel ingress responsibility; the
adapter is an internal application interface, not a public HTTP endpoint.

Offline tests cover direct/bus delivery, both legacy channel routing formats,
invalid routing, missing configuration, mismatched buses, and startup failure.
