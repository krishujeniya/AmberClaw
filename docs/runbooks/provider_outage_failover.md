# Incident Runbook: LLM Provider Outage & Failover

## Overview
When an upstream model provider (e.g., Anthropic, OpenAI, Azure) experiences an outage, AmberClaw's internal `CircuitBreaker` automatically trips to `OPEN` after 5 consecutive failures, fast-failing traffic to prevent request queuing and resource exhaustion.

## Verification
Confirm the circuit status via logs or dashboard:
```bash
grep -i "CircuitBreaker" logs/AmberClaw.log
```
Sample log output:
```
CircuitBreaker [anthropic] TRIPPED to OPEN state after 5 consecutive failures.
```

## Failover Execution

### Automatic Failover
AmberClaw's router automatically routes subsequent agent executions to configured secondary fallback models (e.g., falling back from `claude-3-7-sonnet` to `gpt-4o` or local Ollama).

### Manual Emergency Failover
To force immediate routing to a specific provider:
```bash
# Force switch to OpenAI / Azure
amberclaw config set provider openai
amberclaw config set model gpt-4o

# Or force switch to offline air-gapped Ollama
amberclaw config set provider ollama
amberclaw config set model deepseek-r1:32b
```

## Recovery & Circuit Reset
Once the upstream provider status page reports operational status:
1. Wait 30 seconds for the circuit breaker to enter `HALF_OPEN` probe state.
2. If manual reset is required:
   ```bash
   amberclaw provider reset-circuit --provider anthropic
   ```
