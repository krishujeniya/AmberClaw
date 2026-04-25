# Security Policy

## Reporting Vulnerabilities

Found a security hole in AmberClaw? Here is how to report it:

1. **Do not** open a public GitHub issue.
2. File a private security advisory on GitHub, or reach out directly to the maintainer (Krish Ujeniya).
3. Include in your report:
   - What the vulnerability is
   - How to reproduce it
   - What damage it could cause
   - A fix suggestion, if you have one

We target a 48-hour response time.

## Security Best Practices

### 1. API Key Management

**Never commit API keys to version control.**

```bash
# Correct: lock down the config file
chmod 600 ~/.AmberClaw/config.json

# Wrong: hard-coding keys or checking them in
```

Recommendations:
- Keep API keys in `~/.AmberClaw/config.json` with permissions set to `0600`
- Environment variables work too for sensitive values
- Use an OS keyring or credential manager in production
- Rotate your keys on a regular schedule
- Maintain separate keys for dev and prod environments

### 2. Channel Access Control

**Always set up `allowFrom` lists before going live.**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["123456789", "987654321"]
    },
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

Notes:
- Before version 0.1.4.post4, leaving `allowFrom` empty meant anyone could connect. From 0.1.4.post4 onward, an empty list blocks everyone — set `["*"]` if you actually want open access.
- Grab your Telegram user ID from `@userinfobot`
- WhatsApp numbers need the full country code
- Check access logs regularly for unauthorized attempts

### 3. Shell Command Execution

The `exec` tool runs shell commands. Dangerous patterns are filtered, but you should still:

- ✅ Review tool usage in agent logs
- ✅ Know what commands the agent is running
- ✅ Run under a dedicated, low-privilege user account
- ✅ Never run AmberClaw as root
- ❌ Do not disable built-in security checks
- ❌ Do not run on machines with sensitive data unless you have reviewed the risks

Blocked command patterns:
- `rm -rf /` and similar root-level deletions
- Fork bombs
- Filesystem formatting (`mkfs.*`)
- Direct disk writes
- Other obviously destructive operations

### 4. File System Access

File operations include path traversal protection. Additional precautions:

- ✅ Run with a dedicated user account
- ✅ Use filesystem permissions to fence off sensitive directories
- ✅ Audit file operations in your logs periodically
- ❌ Do not hand the agent unrestricted access to important files

### 5. Network Security

**API traffic:**
- All outbound API calls default to HTTPS
- Timeouts are configured to prevent hung requests
- Consider firewall rules to limit outbound connections if your threat model calls for it

**WhatsApp bridge:**
- Binds to `127.0.0.1:3001` only — not reachable from the network
- Set `bridgeToken` in config for shared-secret auth between Python and Node.js
- Keep `~/.AmberClaw/whatsapp-auth` secured at mode `0700`

### 6. Dependency Security

**Keep your dependencies current.**

```bash
# Check for known vulnerabilities
pip install pip-audit
pip-audit

# Pull the latest version
pip install --upgrade amberclaw-ai
```

For Node.js components (WhatsApp bridge):
```bash
cd bridge
npm audit
npm audit fix
```

Notes:
- Always use the latest `litellm` release for security patches
- The `ws` dependency was bumped to 8.17.1 or later to close a DoS vector
- Run `pip-audit` or `npm audit` as part of your routine
- Subscribe to security advisories for AmberClaw and its dependencies

### 7. Production Deployment

For production environments:

1. **Isolate the runtime**
   ```bash
   # Run inside a container or VM
   docker run --rm -it python:3.11
   pip install amberclaw-ai
   ```

2. **Use a dedicated user**
   ```bash
   sudo useradd -m -s /bin/bash amberclaw
   sudo -u amberclaw amberclaw gateway
   ```

3. **Set permissions**
   ```bash
   chmod 700 ~/.AmberClaw
   chmod 600 ~/.AmberClaw/config.json
   chmod 700 ~/.AmberClaw/whatsapp-auth
   ```

4. **Enable logging**
   ```bash
   tail -f ~/.AmberClaw/logs/AmberClaw.log
   ```

5. **Enforce rate limits**
   - Configure limits on your API providers
   - Watch for usage anomalies
   - Set spending caps on LLM APIs

6. **Stay updated**
   ```bash
   # Check for updates weekly
   pip install --upgrade amberclaw-ai
   ```

### 8. Dev vs Prod

**Development:**
- Use throwaway API keys
- Work with non-sensitive data only
- Turn on verbose logging
- Use a test bot on Telegram

**Production:**
- Use dedicated keys with spending caps
- Lock down filesystem access
- Enable audit-level logging
- Review security posture on a regular cadence
- Monitor for anomalous behavior

### 9. Data Privacy

- Log files can contain sensitive content — protect them accordingly
- LLM providers see your prompts — read their privacy policies
- Chat history is stored locally in `~/.AmberClaw` — protect that directory
- API keys sit in plain text — use an OS keyring in production

### 10. Incident Response

If you suspect a breach:

1. **Revoke any compromised API keys immediately**
2. **Search logs for unauthorized access**
   ```bash
   grep "Access denied" ~/.AmberClaw/logs/AmberClaw.log
   ```
3. **Check for unexpected file modifications**
4. **Rotate every credential**
5. **Update to the latest release**
6. **Notify the maintainers**

## Security Features

### Built-in controls

✅ **Input validation**
- Path traversal protection on file operations
- Detection of dangerous command patterns
- Length limits on HTTP request inputs

✅ **Authentication**
- Allow-list access control — empty `allowFrom` blocks all since 0.1.4.post4 (use `["*"]` to open it)
- Failed auth attempts are logged

✅ **Resource limits**
- Command execution timeout: 60 seconds by default
- Output truncation at 10 KB
- HTTP request timeouts: 10–30 seconds

✅ **Encrypted transport**
- HTTPS for every external API call
- TLS for the Telegram API
- WhatsApp bridge: localhost-only binding plus optional token auth

## Known Limitations

⚠️ Current gaps:

1. **No rate limiting** — users can send unlimited messages (add your own if needed)
2. **Plain-text config** — API keys are not encrypted at rest (use a keyring in production)
3. **No session expiry** — sessions do not time out automatically
4. **Basic command filtering** — only catches obvious destructive patterns
5. **Limited audit trail** — security event logging is minimal (extend as needed)

## Pre-Deployment Checklist

Before putting AmberClaw into production:

- [ ] API keys stored outside of source code
- [ ] Config file permissions set to 0600
- [ ] `allowFrom` configured for every channel
- [ ] Running under a non-root account
- [ ] File system permissions locked down
- [ ] Dependencies updated to latest secure versions
- [ ] Log monitoring in place
- [ ] Rate limits set on API providers
- [ ] Backup and recovery plan documented
- [ ] Custom skills and tools reviewed for security

## Updates

**Last revised**: 2026-04-25

Stay current:
- GitHub Security Advisories: https://github.com/krishujeniya/AmberClaw/security/advisories
- Release Notes: https://github.com/krishujeniya/AmberClaw/releases

## License

See the LICENSE file for details.
