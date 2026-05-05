---
name: claude-read-first-enforcer
description: Strict safety rule: read before write. Use when working on complex or sensitive codebases.
---

@claude-read-first-enforcer

# Read-Before-Edit Protocol

You are FORBIDDEN from modifying any file that has not been read in the current turn or the immediate previous turn.

## Protocol:
1. `view_file` the target file.
2. Analyze the specific line range.
3. Only then invoke `replace_file_content` or `multi_replace_file_content`.

Failure to follow this sequence will result in a validation error.
