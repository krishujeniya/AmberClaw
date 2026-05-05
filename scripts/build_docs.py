import os

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content.strip() + "\n")

write("mkdocs.yml", """
site_name: AmberClaw Documentation
theme:
  name: material
plugins:
  - search
  - mkdocstrings:
      default_handler: python
nav:
  - Home: index.md
  - Getting Started:
    - Setup: setup.md
    - Windows Setup: windows-setup.md
  - Architecture: architecture.md
  - Guides:
    - Troubleshooting: troubleshooting.md
    - Building Skills: skills.md
    - Comparisons: comparisons.md
  - API Reference: api.md
""")

write("docs/index.md", "# Welcome to AmberClaw\nSee README.")
write("docs/setup.md", "# Setup\nSee README.")

write("docs/architecture.md", """
# Architecture Deep-Dive

Message flow:
1. **user message**: Received from the chat platform.
2. **channel**: Adapter parses it.
3. **bus**: Routes the message.
4. **agent**: Processes intent.
5. **tool**: Executes actions.
6. **memory**: Persists context.
7. **response**: Sent back to user.

![Architecture](../assets/AmberClaw_arch.png)
""")

write("docs/troubleshooting.md", """
# Troubleshooting

1. **WhatsApp Node.js**: Needs Node.js >= 18. Update via nvm.
2. **Feishu/DingTalk Firewall**: Ensure WebSockets/Streams are unblocked on corp networks.
3. **Matrix Homeserver**: Use valid access token and matrix server URL.
4. **Provider Auth**: Ensure `*_API_KEY` env vars are correct.
5. **Docker Volumes**: Make sure `~/.AmberClaw` is mounted properly (`-v ~/.AmberClaw:/root/.amberclaw`).
6. **UV Install**: Run `uv tool update` if paths are stale.
7. **Port Conflicts**: Gateway uses 18790. Change if occupied.
8. **Rate Limits**: Respect provider limits to avoid 429 errors.
""")

write("docs/windows-setup.md", """
# Windows Setup

1. Install Python 3.11+.
2. `pip install amberclaw`.
3. To run as a background service, use NSSM (Non-Sucking Service Manager):
   `nssm install AmberClawGateway "C:\\path\\to\\amberclaw.exe" gateway`
   `nssm start AmberClawGateway`
""")

write("MIGRATION.md", """
# Migration Guide

## Upgrading to 1.x
- Configs now live in `~/.AmberClaw/config.json`.
""")

write("docs/skills.md", """
# Building Skills
Directory structure requires `SKILL.md` (manifest) and `__init__.py`.
Publish to ClawHub by creating a PR.
""")

write("docs/comparisons.md", """
# vs Alternatives

| Feature | AmberClaw | LangChain | CrewAI | AutoGen | Open WebUI |
|---|---|---|---|---|---|
| LOC | ~4k | >50k | ~15k | ~20k | UI-Heavy |
| Speed | Fast | Med | Med | Med | Med |
""")

write("docs/api.md", "# API Reference\n::: amberclaw")

write("examples/configs/config.telegram-claude.json", '{"channels":{"telegram":{"enabled":true,"token":"TOKEN"}}}')
write("examples/configs/config.discord-local.json", '{"channels":{"discord":{"enabled":true,"token":"TOKEN"}}}')
write("examples/configs/config.whatsapp-openai.json", '{"channels":{"whatsapp":{"enabled":true}}}')

for d in ["basic_agent", "custom_skill", "mcp_filesystem", "multi_agent", "whatsapp", "rag_pipeline", "cron_task", "heartbeat", "custom_provider", "docker_compose"]:
    write(f"examples/{d}/README.md", f"# {d}\nRun this example.")
    write(f"examples/{d}/main.py", f"# {d}")

print("Docs structure created.")
