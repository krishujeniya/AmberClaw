# CL-022: Controlled Comparative Benchmark Reproduction Guide

## 1. Experimental Environment and Pinned Parameters
To ensure strict reproducibility, all comparative benchmark runs are conducted under identical resource constraints:

- **Host Architecture**: Linux x86_64, kernel >= 6.1.
- **Hardware Budget**: 4 vCPU, 3.3 GB Host RAM, NVMe SSD storage with Write-Ahead Logging.
- **Model Inferences**:
  - Cloud baseline: Claude 3.5 Sonnet (`temperature=0.0`, `top_p=1.0`, `max_tokens=1024`).
  - Local baseline: Qwen 2.5 7B Instruct via local Ollama instance (`num_ctx=8192`, `temperature=0.0`).
- **Random Seed**: `42` pinned across all data partitions and pseudo-random generators.

## 2. Benchmark Tasks
Each system is evaluated against 5 standardized operational tasks executed in triplicate (3 runs per task, 15 attempts per system, 75 runs total):

1. **T1 (Cited Knowledge)**: Documentation QA with verified span attribution, injection rejection, and contradiction abstention.
2. **T2 (Incident Remediation)**: Log triage and remediation planning with human approval ticket gating.
3. **T3 (Hard Spend Ceilings)**: Pre-execution budget reservation and hard termination upon exceeding the spend cap.
4. **T4 (Crash Recovery)**: Simulating worker process termination midway through multi-step workflows and verifying exact boundary resumption without duplicate side-effects.
5. **T5 (Kernel Containment)**: Verifying that filesystem modifications outside declared paths and unauthorized network egress are blocked at the kernel syscall boundary.

## 3. Reproduction Steps
1. Activate virtual environment:
   ```bash
   source .venv/bin/activate
   ```
2. Execute benchmark test suite:
   ```bash
   pytest -v -o addopts="" tests/unit/benchmarks/test_comparative_runner.py
   ```
3. Inspect generated metrics in `evidence/competitive/CL-022/9ece8c0/comparative-benchmark-report.json`.

## 4. Statistical Analysis Methodology
Confidence intervals for binomial task success are computed using the Wilson score interval:

$$w = \frac{p + \frac{z^2}{2n} \pm z\sqrt{\frac{p(1-p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

Where:
- $n = 15$ total attempts per system.
- $p = \frac{k}{n}$ sample success proportion.
- $z = 1.95996$ (corresponding to a two-sided 95% confidence level).

Zero runs are discarded. Unsupported features (such as the inability to enforce Landlock sandboxing or pre-allocated budget reservations) are explicitly recorded as failures rather than omitted.
