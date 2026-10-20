# ORIGIN — Hackathon Submission & Evaluation Checklist

> **Hackathon Event:** HackOctober MLH × Tech4hack  
> **Submission Deadline:** October 22, 2026, 13:30 GMT+2  
> **Repository:** [https://github.com/ATUMANYIRE/ORIGIN](https://github.com/ATUMANYIRE/ORIGIN)  

---

## 1. Submission Metadata Checklist

- [x] **Project Name:** ORIGIN — Autonomous Scientific Intelligence for Software Systems
- [x] **Tagline:** Give software the ability to understand itself.
- [x] **Repository URL:** `https://github.com/ATUMANYIRE/ORIGIN`
- [x] **License:** MIT License (Open Source)
- [x] **Target Track:** AI / Systems / Reliability / Infrastructure (HackOctober MLH × Tech4hack)
- [x] **Primary Language & Frameworks:** Python 3.12 (FastAPI), Next.js 15 (React 19, TypeScript), PostgreSQL 16, Redis 7, OpenTelemetry
- [x] **Devpost Project Description:** Fully prepared in [`submission/PROJECT_DESCRIPTION.md`](file:///E:/Projects/ORIGIN/submission/PROJECT_DESCRIPTION.md)
- [x] **Video Demonstration Script:** Fully prepared in [`submission/DEMO_SCRIPT.md`](file:///E:/Projects/ORIGIN/submission/DEMO_SCRIPT.md)
- [x] **Video Recording Instructions:** Documented in [`submission/VIDEO_PRODUCTION.md`](file:///E:/Projects/ORIGIN/submission/VIDEO_PRODUCTION.md)
- [x] **Visual Assets / Screenshots:** 8 high-resolution 1440×900 screenshots captured in [`submission/SCREENSHOTS/`](file:///E:/Projects/ORIGIN/submission/SCREENSHOTS/)

---

## 2. Code Quality & Security Audit

- [x] **Zero Private Credentials or API Keys:** Verified via `scripts/audit-security.py` scanning 147 source files.
- [x] **Clean Production Build:** Next.js production build (`next build`) compiles 12 routes with zero TypeScript or ESLint errors.
- [x] **Strict Type Checking:** `mypy app` passes with 0 issues across 50 backend Python files.
- [x] **Linter Compliance:** `ruff check app tests alembic` passes with 0 errors.
- [x] **Database Migrations:** Clean Alembic migration history (`0001_initial` through `0004_recovery_safety`).
- [x] **Automated Acceptance Suite:** All 8 verification steps in `scripts/verify-all.ps1` execute and pass with exit code 0.

---

## 3. Scientific Integrity & Empirical Rigor

- [x] **Zero Decorative Metrics:** Every displayed metric, chart, and event originates from live database observations, OpenTelemetry spans, or active simulations.
- [x] **Zero Ground-Truth Leakage:** Verified by `tests/test_scientific_integrity.py` proving no internal simulator fault states leak into telemetry observations.
- [x] **Epistemic Blinding:** Investigator service operates without knowledge of injected fault parameters.
- [x] **Honest Inconclusive Reporting:** Ambiguous multi-service noise is honestly flagged as `INCONCLUSIVE` rather than guessing a false positive.
- [x] **Predictive Uncertainty:** Digital Twin counterfactual projections provide empirical 95% confidence intervals via Monte Carlo calibration.
- [x] **Traceability Matrix:** 15/15 product claims mapped to automated verification tests in [`docs/TRACEABILITY_MATRIX.md`](file:///E:/Projects/ORIGIN/docs/TRACEABILITY_MATRIX.md).

---

## 4. Operational Reproducibility Runbook for Evaluators

Evaluators can reproduce all results in under 5 minutes on any modern workstation with Docker:

```bash
# 1. Clone repository
git clone https://github.com/ATUMANYIRE/ORIGIN.git
cd ORIGIN

# 2. Configure production environment
cp .env.production.example .env.production

# 3. Launch the full stack
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# 4. Open in browser
# Application Interface: http://localhost
# Interactive Guided Demo: http://localhost/demo
# OpenAPI Backend Docs: http://localhost/docs

# 5. Run full automated verification suite
powershell.exe -ExecutionPolicy Bypass -File scripts/verify-all.ps1
```
