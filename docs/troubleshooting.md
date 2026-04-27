# Troubleshooting

Here are common issues and solutions:

1. **WhatsApp Node.js Dependency**: Requires Node.js 18 or newer. Update using nvm or your package manager.
2. **Feishu/DingTalk Firewall Issues**: Ensure WebSockets and Stream Mode ports are unblocked on your corporate firewall.
3. **Matrix Homeserver Setup**: Use your exact Matrix homeserver URL and a valid access token.
4. **Provider Auth Errors**: Double-check `*_API_KEY` variables in `.env` or `config.json`.
5. **Docker Volume Mounting**: Ensure `~/.AmberClaw` is mounted properly, e.g., `-v ~/.AmberClaw:/root/.amberclaw`.
6. **Port Conflicts**: Gateway uses 18790 by default. Change it if occupied.
7. **UV Install Errors**: Run `uv tool update` if your environment paths are stale.
8. **Rate Limits**: Respect the provider limits (e.g., 429 Too Many Requests). Implement custom backoff if necessary.
