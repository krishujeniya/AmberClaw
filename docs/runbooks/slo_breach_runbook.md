# Incident Runbook: Service Level Objective (SLO) Breach

## Overview
This runbook guides on-call engineers when an automated alert fires indicating that AmberClaw's rolling availability has dropped below 99.9% or P95 latency has exceeded 1,000ms.

## Diagnostic Steps

### 1. Check Live SLO & Health Metrics
Execute via AmberClaw CLI:
```bash
amberclaw doctor
```
Or query the Prometheus metrics exposition endpoint:
```bash
curl -s http://127.0.0.1:8000/metrics | grep -E "amberclaw_http|amberclaw_llm"
```

### 2. Inspect In-Flight Circuit Breakers
Review circuit breaker states across all LLM providers:
```bash
curl -s http://127.0.0.1:8000/api/metrics/usage
```
- If a circuit breaker is in `OPEN` state, requests to that provider are fast-failing. See `provider_outage_failover.md`.

### 3. Check Audit Logs & Error Tracker
```bash
amberclaw audit verify --log-file logs/audit.jsonl
tail -n 100 logs/audit.jsonl | jq '.action, .outcome'
```

## Remediation Actions
1. **High Latency (>1000ms)**:
   - Check if rate limits are being throttled by upstream providers.
   - Switch active default model to low-latency fast model:
     ```bash
     amberclaw config set model gpt-4o-mini
     ```
2. **Elevated 5xx Errors**:
   - Check if Redis/PostgreSQL or ChromaDB is reachable:
     ```bash
     docker compose -f deploy/docker/docker-compose.prod.yml ps
     ```
   - Restart unresponsive microservices:
     ```bash
     docker compose -f deploy/docker/docker-compose.prod.yml restart amberclaw-gateway
     ```
