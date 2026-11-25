# CL-019: Rejected Hypotheses and Positioning Adjustments

## 1. Executive Summary
This document synthesizes findings from 10 prospective buyer discovery interviews across regulated enterprise sectors. The findings mandate concrete product adjustments: narrowing scope away from a monolithic "all-purpose agent" towards scoped, air-gapped private-operations recipes with deterministic audit guarantees.

## 2. Tested Hypotheses & Outcomes

### Hypothesis 1: Verifiable Air-Gapped Egress Control (VALIDATED)
- **Validation**: 8 of 10 participants identified data exfiltration risks as their primary obstacle in adopting commercial agent frameworks.
- **Action**: Landlock filesystem sandboxing and seccomp network egress blocks (CL-006, CL-007) are confirmed as primary product differentiators.

### Hypothesis 2: Durable Execution & Approval Survival (VALIDATED)
- **Validation**: 7 of 10 participants reported production incidents caused by agents silently repeating mutations or losing state during process restarts.
- **Action**: Durable run state machines with idempotency keys and crash recovery (CL-011) remain standard across all supported recipes.

### Hypothesis 3: Hard Budgets and Cost per Success (VALIDATED)
- **Validation**: 6 of 10 participants expressed frustration with unpredictable token billing in agent runaways.
- **Action**: Pre-execution budget reservations and cost-per-success metrics (CL-015) remain enforced.

### Hypothesis 4: Universal Multi-Agent Chat Assistant (REJECTED)
- **Rejection Evidence**: 9 of 10 participants rejected replacing existing terminal workflows and script pipelines with an all-encompassing chat assistant.
- **Correction**: Abandon the positioning of AmberClaw as a "universal personal assistant". Focus exclusively on targeted operational recipes (incident investigation, knowledge extraction, and scheduled reporting) that integrate directly into existing CLI and API pipelines.

### Hypothesis 5: Bundled Proprietary Model Weights (REJECTED)
- **Rejection Evidence**: Enterprise security policies prohibit black-box model binaries. 100% of respondents demanded Bring-Your-Own-Model (BYOM) support via local inference (Ollama/vLLM) or existing corporate API gateways.
- **Correction**: Decouple inference layers completely; eliminate any plans for proprietary weight distributions.
