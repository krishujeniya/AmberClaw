# CL-026: Extension Contract, Manifest Specification, and Lifecycle

## 1. Extension Manifest Specification (`plugin.yaml`)
AmberClaw extensions are packaged as standalone directory structures containing a declarative `plugin.yaml` manifest and an entrypoint script.

```yaml
name: custom_integration_name
version: 1.0.0
description: "Brief functional summary of third-party integration"
entrypoint: main.py
capabilities:
  - filesystem_read
  - network_access
min_amberclaw_version: "2026.0.1"
author: "Engineering Organization Name"
license: "Apache-2.0"
```

### 1.1 Capability Enumeration
Extensions run in restricted subprocess environments and must request discrete permissions:
- `filesystem_read`: Read access restricted strictly to `./workspace` and the extension's local directory.
- `filesystem_write`: Write access restricted to declared sandbox output directories; system paths remain immutable via Landlock.
- `network_access`: Network socket creation governed by the system egress controller and DNS interceptor.
- `env_read`: Access to non-sensitive environment variables; secrets and administrative API keys are filtered.

## 2. Extension Lifecycle Operations
- **Install**:
  1. Operator copies extension package into configured extensions directory (`plugins_dir`).
  2. Manifest is parsed and validated against `PluginManifest` schema.
  3. Entrypoint syntax and declared capabilities are checked.
- **Update**:
  1. Updated manifest with incremented semver (`e.g. 1.0.0 -> 1.1.0`) is discovered automatically upon next scan.
  2. Running child subprocesses are recycled gracefully upon idle.
- **Revoke**:
  1. Removal or disabling of `plugin.yaml` removes all registered tools immediately from the active registry.
  2. Active connections are terminated; subsequent tool invocations return `ToolNotFoundError`.

## 3. Mandatory Human Approval for Extension Mutations
Any tool registered by a third-party extension with risk level `MEDIUM`, `HIGH`, or `CRITICAL` (including all filesystem write and outbound network operations) cannot execute autonomously. It is intercepted by `ToolApprovalManager` and requires an operator approval ticket before dispatch.
