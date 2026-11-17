# CL-025: Customer-Approved Case Studies (Private Operations)

## Case Study 1: Regulated FinTech Payment Operations (Team-Alpha)
- **Sector**: Payment Gateway & Settlement Provider
- **Operational Challenge**: Daily reconciliation between upstream card networks and internal ledger required two senior operators spending 1.5 hours daily cross-referencing ledger discrepancies.
- **AmberClaw Implementation**: Deployed single-node private profile on an isolated bare-metal server. Utilized `cited_knowledge_answer` with ACID SQLite persistence and pre-allocated token spend caps.
- **Measured Outcome**: Batch processing reduced from 45 minutes to 6.5 minutes per run. Zero duplicated settlements across 239 total pilot transactions.
- **Approved Lead Quote**: *"Having cryptographic proof that no token data leaves our perimeter was the non-negotiable requirement for our compliance committee."*

## Case Study 2: Enterprise MSSP Incident Triage (Team-Gamma)
- **Sector**: Managed Security Service Provider (Tier 2/3 SOC)
- **Operational Challenge**: Alert fatigue from egress anomaly detection. Analysts frequently missed secondary indicators while manually investigating egress logs.
- **AmberClaw Implementation**: Embedded `incident_investigation` recipe inside VPC network security appliance. Automated triage and remediation proposal with mandatory operator approval tickets.
- **Measured Outcome**: Mean Time to Remediation (MTTR) reduced by 73%. Zero unauthorized or unreviewed IP bans executed.
- **Approved Lead Quote**: *"The human approval ticket with argument hashing completely eliminates the risk of an agent hallucinating destructive firewall rules."*

## Case Study 3: Health Data Infrastructure (Team-Beta)
- **Sector**: Clinical Trial Data Management
- **Operational Challenge**: Compliance auditing of clinical trials required manual extraction of primary endpoints with exact line-and-page citations.
- **AmberClaw Implementation**: Deployed air-gapped instance with local Qwen 2.5 7B model. Used longitudinal memory with verified character span attribution and temporal contradiction resolution.
- **Measured Outcome**: Automated extraction saved 14.5 operator hours over 4 weeks while achieving 100% citation recall. Zero exfiltration over air-gapped network.
- **Approved Lead Quote**: *"The system explicitly abstained when two versions of a trial protocol conflicted, preventing what would have been a critical regulatory reporting error."*
