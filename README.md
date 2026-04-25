<div align="center">
  <img src="LogoAC.png" alt="AmberClaw" width="400">

  <h1>AmberClaw</h1>
  <p><strong>Ultra-Lightweight Personal AI Assistant Framework</strong></p>

  <p>
    <a href="https://github.com/krishujeniya/AmberClaw/actions/workflows/ci.yml"><img src="https://github.com/krishujeniya/AmberClaw/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
    <a href="https://pypi.org/project/amberclaw-ai/"><img src="https://img.shields.io/pypi/v/amberclaw-ai?color=blue" alt="PyPI"></a>
    <a href="https://pepy.tech/project/amberclaw-ai"><img src="https://static.pepy.tech/badge/amberclaw-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-3776AB?logo=python&logoColor=white" alt="Python">
    <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  </p>

  <p>
    <a href="#-quick-start">Quick Start</a> •
    <a href="#-features">Features</a> •
    <a href="#-chat-integrations">Integrations</a> •
    <a href="#-configuration">Configuration</a> •
    <a href="#-docker">Docker</a> •
    <a href="#-contributing">Contributing</a>
  </p>
</div>

---

**AmberClaw** is a production-grade, ultra-lightweight personal AI assistant that delivers core agentic functionality with ~4,000 lines of code. Connect it to any LLM provider, plug it into your favorite chat platform, and let it work for you.

## ✨ Features

| Category | Capabilities |
|----------|-------------|
| 🧠 **Agent Core** | Agentic loop, tool execution, sub-agent spawning, memory, skills |
| 🤖 **Multi-Provider** | OpenRouter, Anthropic, OpenAI, Gemini, DeepSeek, Groq, Azure, vLLM, and more |
| 💬 **Chat Platforms** | Telegram, Discord, WhatsApp, Slack, Feishu, DingTalk, Email, QQ, Matrix |
| 🔌 **MCP Support** | Model Context Protocol for external tool servers |
| ⏰ **Automation** | Heartbeat tasks, cron jobs, scheduled workflows |
| 🐳 **Deployment** | Docker, docker-compose, systemd, multi-instance |
| 🔒 **Security** | Allow-list access control, command filtering, path traversal protection |

## 🏗️ Architecture

<p align="center">
  <img src="AmberClaw_arch.png" alt="AmberClaw Architecture" width="800">
</p>

## 📦 Installation

### From Source (recommended for development)

```bash
git clone https://github.com/krishujeniya/AmberClaw.git
cd AmberClaw
pip install -e .
```

### With uv (fast, recommended)

```bash
uv tool install amberclaw-ai
```

### From PyPI

```bash
pip install amberclaw-ai
```

### Update

```bash
# pip
pip install -U amberclaw-ai

# uv
uv tool upgrade amberclaw-ai
```

## 🚀 Quick Start

### One-Line Interactive Setup

```bash
python setup.py
```

This configures your AI provider, chat integration, and launches AmberClaw automatically.

### Manual CLI Chat

```bash
amberclaw agent
```

### Start Gateway (for chat integrations)

```bash
amberclaw gateway
```

## 💬 Chat Integrations

| Platform | Setup Required |
|----------|---------------|
| **Telegram** | Bot token from @BotFather |
| **Discord** | Bot token + Message Content intent |
| **WhatsApp** | QR code scan (requires Node.js ≥18) |
| **Slack** | Bot token + App-Level token (Socket Mode) |
| **Feishu** | App ID + App Secret (WebSocket) |
| **DingTalk** | App Key + App Secret (Stream Mode) |
| **Email** | IMAP/SMTP credentials |
| **QQ** | App ID + App Secret |
| **Matrix** | User ID + Access Token |
| **Mochat** | Auto-setup via agent message |

<details>
<summary><b>Telegram Setup</b></summary>

1. Create a bot via `@BotFather` on Telegram → copy the token
2. Add to `~/.AmberClaw/config.json`:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

3. Run `amberclaw gateway`

</details>

<details>
<summary><b>Discord Setup</b></summary>

1. Create application at [discord.com/developers](https://discord.com/developers/applications)
2. Enable **MESSAGE CONTENT INTENT** in Bot settings
3. Add to config:

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"],
      "groupPolicy": "mention"
    }
  }
}
```

4. Invite bot to server → run `amberclaw gateway`

</details>

<details>
<summary><b>WhatsApp Setup</b></summary>

```bash
amberclaw channels login    # Scan QR code
amberclaw gateway           # Start gateway
```

Config:
```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

</details>

<details>
<summary><b>Other Platforms</b></summary>

See the full configuration reference in `~/.AmberClaw/config.json`. Each platform follows the same pattern:
1. Obtain credentials from the platform
2. Add channel config with `enabled: true` and `allowFrom` list
3. Run `amberclaw gateway`

</details>

## ⚙️ Configuration

Config file: `~/.AmberClaw/config.json`

### Providers

| Provider | Purpose | Get API Key |
|----------|---------|-------------|
| `openrouter` | LLM (all models) | [openrouter.ai](https://openrouter.ai) |
| `anthropic` | Claude direct | [console.anthropic.com](https://console.anthropic.com) |
| `openai` | GPT direct | [platform.openai.com](https://platform.openai.com) |
| `gemini` | Gemini direct | [aistudio.google.com](https://aistudio.google.com) |
| `deepseek` | DeepSeek direct | [platform.deepseek.com](https://platform.deepseek.com) |
| `groq` | LLM + Whisper | [console.groq.com](https://console.groq.com) |
| `azure_openai` | Azure OpenAI | [portal.azure.com](https://portal.azure.com) |
| `custom` | Any OpenAI-compatible | — |
| `vllm` | Local/self-hosted | — |

<details>
<summary><b>Adding a New Provider</b></summary>

Two-step process:

1. Add `ProviderSpec` to `amberclaw/providers/registry.py`:

```python
ProviderSpec(
    name="myprovider",
    keywords=("myprovider",),
    env_key="MYPROVIDER_API_KEY",
    display_name="My Provider",
    litellm_prefix="myprovider",
)
```

2. Add field to `ProvidersConfig` in `amberclaw/config/schema.py`:

```python
myprovider: ProviderConfig = ProviderConfig()
```

Everything else (env vars, model prefixing, status display) works automatically.

</details>

### MCP (Model Context Protocol)

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "remote-server": {
        "url": "https://example.com/mcp/",
        "headers": { "Authorization": "Bearer xxxxx" }
      }
    }
  }
}
```

### Security

| Option | Default | Description |
|--------|---------|-------------|
| `tools.restrictToWorkspace` | `false` | Sandbox all agent tools to workspace directory |
| `channels.*.allowFrom` | `[]` (deny all) | Whitelist of user IDs. Use `["*"]` to allow everyone |

## 💻 CLI Reference

| Command | Description |
|---------|-------------|
| `amberclaw onboard` | Initialize config & workspace |
| `amberclaw agent` | Interactive chat mode |
| `amberclaw agent -m "..."` | Single message |
| `amberclaw gateway` | Start gateway (connects chat platforms) |
| `amberclaw status` | Show status |
| `amberclaw provider login openai-codex` | OAuth login |
| `amberclaw channels login` | Link WhatsApp |
| `amberclaw channels status` | Show channel status |

## 🐳 Docker

### Docker Compose

```bash
docker compose run --rm amberclaw-cli onboard   # First-time setup
vim ~/.AmberClaw/config.json                     # Add API keys
docker compose up -d amberclaw-gateway           # Start gateway
```

### Docker

```bash
docker build -t amberclaw .
docker run -v ~/.AmberClaw:/root/.amberclaw -p 18790:18790 amberclaw gateway
```

## 🐧 Linux Service

```ini
# ~/.config/systemd/user/amberclaw-gateway.service
[Unit]
Description=AmberClaw Gateway
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/amberclaw gateway
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now amberclaw-gateway
```

## 📁 Project Structure

```
amberclaw/
├── agent/          # 🧠 Core agent logic (loop, context, memory, skills, tools)
├── bus/            # 🚌 Message routing
├── channels/       # 📱 Chat platform integrations
├── cli/            # 🖥️ CLI commands
├── config/         # ⚙️ Configuration (Pydantic models)
├── cron/           # ⏰ Scheduled tasks
├── data/           # 📊 Data science module (optional)
├── engine/         # ⚡ Execution engine
├── features/       # 🎯 Feature modules
├── heartbeat/      # 💓 Proactive wake-up system
├── platforms/      # 🌐 Platform adapters
├── providers/      # 🤖 LLM provider registry
├── session/        # 💬 Conversation sessions
├── skills/         # 🎯 Bundled skills
├── superpowers/    # 🦸 Extended capabilities
├── templates/      # 📝 Prompt templates
└── utils/          # 🔧 Utilities
```

## 🤝 Contributing

PRs welcome! The codebase is intentionally small and readable.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Roadmap

- [ ] **Multi-modal** — Images, voice, video understanding
- [ ] **Long-term memory** — Never forget important context
- [ ] **Better reasoning** — Multi-step planning and reflection
- [ ] **More integrations** — Calendar, productivity tools
- [ ] **Self-improvement** — Learn from feedback and mistakes

### Contributors

<a href="https://github.com/krishujeniya/AmberClaw/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=krishujeniya/AmberClaw&max=100&columns=12" alt="Contributors" />
</a>

## ⭐ Star History

<div align="center">
  <a href="https://star-history.com/#krishujeniya/AmberClaw&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=krishujeniya/AmberClaw&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=krishujeniya/AmberClaw&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=krishujeniya/AmberClaw&type=Date" />
    </picture>
  </a>
</div>

## 📄 License

[MIT](LICENSE) © 2026 Krish Ujeniya

---

<p align="center">
  <sub>AmberClaw is for educational, research, and technical exchange purposes only</sub>
</p>
