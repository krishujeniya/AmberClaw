# Building Agent Skills & Tools

AmberClaw features an extensible, type-safe plugin and skill architecture based on Pydantic schemas and dynamic tool registration.

---

## 🛠️ Defining a Custom Tool

Tools inherit from `amberclaw.tools.registry` and specify their input arguments as Pydantic models:

```python
from pydantic import BaseModel, Field
from amberclaw.tools.registry import register_tool

class CalculatorInput(BaseModel):
    expression: str = Field(description="Mathematical expression to evaluate")

@register_tool(name="calculator", description="Safely evaluate arithmetic expressions")
async def calculate(params: CalculatorInput) -> str:
    # Execution happens inside zero-trust sandbox
    result = eval_safe(params.expression)
    return str(result)
```

---

## 📁 Creating a Skill Bundle

Skills are directories containing instruction manifests and tools:

```
my_skill/
├── SKILL.md          # Skill metadata & invocation guidelines
└── main.py           # Tool definitions & execution handlers
```

### Manifest Format (`SKILL.md`)

```yaml
---
name: web_researcher
version: 1.0.0
description: Autonomous web search and summarization tools.
capabilities:
  - network_egress
  - filesystem_read
---

# Web Researcher Skill
Provides search queries via DuckDuckGo and fetches clean text representations.
```

---

## 🔒 Security Constraints for Tools

Every tool executed by an agent is subject to zero-trust policies:
- **Filesystem Isolation**: Restricted to workspace paths via Landlock LSM.
- **Egress Firewall**: Network requests must be whitelisted.
- **Secret Redaction**: API keys and passwords in tool parameters and outputs are scrubbed automatically.
- **Human Approval**: Dangerous tools can be flagged with `@require_approval` to route through the governance queue.
