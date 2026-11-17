# CL-025: Measured Workflow Duration and Operator Time Savings

## 1. Measurement Methodology
Operator active duration was measured across 4 cohorts comparing baseline operational processes against AmberClaw's private operations recipes. Measurements capture total human touch-time from initial trigger to task completion.

## 2. Before vs. After Time Comparison

| Cohort & Workflow | Baseline Process | AmberClaw Recipe | Baseline Time (Mean) | AmberClaw Time (Mean) | Human Time Saved | Efficiency Multiplier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FinOps Ledger Reconciliation** | Manual CSV export, script parsing, spreadsheet diffing, email signoff | `cited_knowledge_answer` + automated ledger verification | 45.0 minutes / batch | 6.5 minutes / batch (review & approve) | 38.5 minutes (85.6%) | **6.9x** |
| **SecOps Alert Triage & Remediation** | Log aggregation query, manual IP lookup, command-line firewall entry | `incident_investigation` + ticket review gate | 32.0 minutes / incident | 4.2 minutes / incident (review ticket) | 27.8 minutes (86.9%) | **7.6x** |
| **HealthInfra Clinical QA Extraction** | Manual document review, page search, manual citation formatting | `cited_knowledge_answer` with verified character spans | 60.0 minutes / report | 11.0 minutes / report (validation check) | 49.0 minutes (81.7%) | **5.5x** |
| **PlatformDev Idle Cloud Resource Cleanup** | Periodic manual AWS console inspection, Slack pings, manual CLI delete | `scheduled_report` with operator approval ticket | 25.0 minutes / weekly cycle | 3.5 minutes / cycle (approval click) | 21.5 minutes (86.0%) | **7.1x** |

## 3. Support Burden & Abandonment Analysis
- **Initial Week Burden**: 8 total support tickets recorded in Week 1 across all 5 teams. 6 of 8 tickets involved local network binding or Ollama GPU memory allocation.
- **Stabilization**: In Weeks 2 through 4, total support tickets dropped to 2, 0, and 0 respectively for the retained teams.
- **Dropout Transparency**: Team-Epsilon (Legal) ceased operations in Week 2 due to hardware procurement freezes within their enterprise parent. They were included in the total denominator (4/5 retained = 80%).
