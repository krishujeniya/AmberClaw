---
name: claude-todo-tracker
description: Real-time task tracking using TodoWrite pattern. Use to keep execution on track.
---

@claude-todo-tracker

# TodoWrite Task Management

Every response must start with a `TODO` list showing the state of the current task.

## Format:
```
[x] Done task
[/] In-progress task
[ ] Pending task
```

## Rules:
- Update progress at the start of every turn.
- Be atomic with task definitions.
- Ensure the user always knows exactly what step is being executed.
