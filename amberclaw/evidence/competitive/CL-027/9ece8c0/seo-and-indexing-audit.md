# CL-027: Technical SEO, Indexing, and Discoverability Audit

## 1. Audit Overview
This audit evaluates the public-facing documentation and benchmark reporting pages for search engine discoverability, crawlability, structural semantics, and boundary protections.

- **Audited Document:** `evidence/competitive/CL-027/9ece8c0/public-workflow-page.html`
- **Audit Date:** 2026-11-08
- **Commit Baseline:** `9ece8c0`
- **Evaluator:** SEO & Product Quality Engineering

---

## 2. On-Page Metadata & Header Verification

| Parameter | Observed Value | Standard Requirement | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Title Tag** | `Private Operations and Agentic Execution Benchmark \| AmberClaw` (62 chars) | Concise, descriptive, under 70 characters | PASS |
| **Meta Description** | `Controlled benchmarks and reproducible workflow recipes for private agentic execution, featuring audit integrity, egress control, and human oversight.` (150 chars) | Specific, factual, between 120 and 160 characters | PASS |
| **Canonical URL** | `https://amberclaw.org/workflows/private-operations/` | Absolute URL matching production host | PASS |
| **Robots Directive (Public)** | `<meta name="robots" content="index, follow">` | Allow search discovery for public research | PASS |
| **Robots Directive (Dashboard)** | `<meta name="robots" content="noindex, nofollow">` in `src/amberclaw/web/static/index.html` | Prevent indexing of private operations consoles | PASS |
| **OpenGraph Title** | `Private Operations and Agentic Execution Benchmark \| AmberClaw` | Identical to page title | PASS |
| **OpenGraph Description** | Matches meta description | Matches meta description | PASS |
| **OpenGraph Type** | `article` | Semantic content categorization | PASS |
| **Twitter Card** | `summary` | Valid card specification | PASS |

---

## 3. Structural Semantics and Heading Hierarchy
- **H1 Header:** `Controlled Comparative Benchmark & Private Operations Recipes` (exactly 1 instance).
- **H2 Sections:**
  1. `1. Benchmark Protocol and Environment Configuration`
  2. `2. Comparative Benchmark Results`
  3. `3. Three Private-Operations Recipes`
  4. `4. Adoption and Retention Data from 4-Week Bounded Pilots`
  5. `5. Reproducibility and Verification Artifacts`
- **H4 Cards:** Component titles inside grid elements.
- **Hierarchy Assessment:** Valid nested semantic order without skipping levels.
- **Navigation:** Semantic `<header>`, `<nav aria-label="Main Navigation">`, `<main>`, `<article>`, `<section>`, `<footer>`.

---

## 4. Structured Data (Schema.org JSON-LD)
The page embeds a validated JSON-LD `@graph` containing:
1. `SoftwareApplication`:
   - `@id`: `https://amberclaw.org/#software`
   - `name`: `AmberClaw`
   - `applicationCategory`: `DeveloperApplication`
   - `operatingSystem`: `Linux, macOS, Windows`
   - `softwareVersion`: `2026.0.1`
   - `license`: `https://opensource.org/licenses/Apache-2.0`
2. `TechArticle`:
   - `@id`: `https://amberclaw.org/workflows/private-operations/#article`
   - `headline`: `Controlled Comparative Benchmark and Private Operations Recipes`
   - `datePublished`: `2026-11-08T00:00:00Z`
   - `dateModified`: `2026-11-08T00:00:00Z`
   - `publisher`: `AmberClaw Project`

---

## 5. Crawl Boundaries & Private Dashboard Isolation
- **Searchable Pages:** Published documentation (`/docs/`), comparative benchmark reports (`/benchmarks/`), and operational recipes (`/recipes/`).
- **Excluded Routes:** Internal web dashboard (`/`), tenant APIs (`/api/v1/`), telemetry streaming (`/events/`), and sandbox artifact mirrors. All marked with explicit `noindex, nofollow` headers and excluded in `robots.txt`.

---

## 6. Claim Attribution & Integrity Policy
- Every quantitative claim (100% success rate, 14.85s p95 latency, $0.0031 cost per success) is attributed directly to:
  - Specific task suite: 5 standardized operations in triplicate.
  - Execution commit: `9ece8c0`.
  - Date of record: `2026-11-08`.
  - Constrained hardware baseline: 4 vCPU, 8 GB RAM, Qwen 2.5 7B GGUF.
- Comparative numbers for rival platforms (Agent Zero, OpenClaw, Dify, Langflow) reference explicit pinned version tags and identically budgeted execution runs.
- No unsubstantiated superiority adjectives or ranking predictions are made.
