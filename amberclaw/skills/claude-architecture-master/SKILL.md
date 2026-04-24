---
name: claude-architecture-master
description: Codebase mapping and architectural maintenance. Use to prevent architectural drift.
---

@claude-architecture-master

# Architectural Context Management

Automatically maintain a semantic understand of the project.

## Requirements:
- Build a `.planning/codebase/MAP.md` if it doesn't exist.
- Track cross-file dependencies and core abstractions.
- Audit every significant change against the established architecture.
- Warn if a proposed change violates existing patterns.
