# LegalLens — Implementation Plan

**Theme:** AI for Legal Assistance & Access · **Branch:** `feat/project-foundation` · **Status:** Production-ready (Phases 0–9 complete) · Verified 2026-09-26

## What it is

LegalLens is a GenAI web app that lets a non-lawyer upload a contract, lease, or policy and get it simplified, risk-flagged, compared against another document, questioned in a grounded chat, and exported as an action checklist or lawyer-prep brief — without generating legal advice.

## Build status

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffolding — Docker Compose, CI skeleton, health endpoint | ✅ |
| 1 | Auth (JWT, argon2id) + document upload (S3/MinIO, magic-byte validation) | ✅ |
| 2 | Text extraction + OCR fallback + chunking + Voyage AI embeddings (pgvector) | ✅ |
| 3 | Plain-language simplification + clause/risk extraction | ✅ |
| 4 | Document Q&A (RAG chat, mandatory citations) | ✅ |
| 5 | Comparison engine + export (summary/checklist/lawyer-brief) | ✅ |
| 6 | Celery async workers, PDF/DOCX renderers wired end-to-end | ✅ |
| 7 | Test suite (287 tests, 80% coverage) + golden-dataset LLM eval harness | ✅ |
| 8 | CI/CD (5-job pipeline), security hardening, staging/prod workflows, monitoring | ✅ |
| 9 | MFA (TOTP), account lockout, CAPTCHA (hCaptcha), CSP headers | ✅ |

**Total**: 25+ REST endpoints (auth, documents, chat, comparisons, exports, MFA) · 395 tests · 13 security layers

## Problem statement → what's built

| Challenge asks for | LegalLens delivers | Where |
|---|---|---|
| Simplifying complex legal documents | 3 reading levels (elementary / plain-English / detailed); map-reduce for long docs | `POST /documents/{id}/simplify` → `services/simplification.py` |
| Comparing contracts, agreements, or policies | Clause-aligned diff across 2–5 docs, materiality rating (none→critical) | `POST /comparisons` → `services/comparison.py` |
| Highlighting clauses, obligations, risks, inconsistencies | 10 clause types × 3 risk levels with rationale (keyword pre-filter + LLM classification) | `POST /documents/{id}/extract-clauses` → `services/clause_extraction.py` |
| Answering questions based on provided documents | RAG chat, top-8 retrieval, every answer carries ≥1 resolvable citation | `POST /chat/sessions/{id}/messages` → `services/chat.py` |
| Understanding options and next steps | Action checklist export, ranked by risk | `POST /exports` (type=`checklist`) |
| Summaries, checklists, actionable outputs | Summary / checklist / lawyer-brief / comparison-report, each as PDF, DOCX, or Markdown | `services/export.py` + `services/renderers/` |
| Preparing info/questions for a legal professional | Standalone lawyer-prep brief generator (not a referral mechanism, by design) | `_generate_lawyer_brief_md()` in `export.py` |

## Verify in 2 minutes

```bash
docker compose -f infra/docker-compose.yml up --build
curl http://localhost:8000/health          # → {"status":"ok"}
```
Then: register → upload a contract → `/simplify` → `/extract-clauses` → open `/chat` and ask a question → export a checklist.

## Explicitly out of scope (by design, not by omission)

Legal advice/case-outcome prediction, e-signature/redlining, multi-language documents, team workspaces, live attorney booking — all documented up front as non-goals for this theme, not gaps.

## Why this document exists

The prior `implementation_plan.md`/`README.md` were written at Phase 0 and never updated as Phases 1–8 shipped, so they still described the project as scaffolding-only. That staleness — not missing functionality — is what this document (and the accompanying prompt) fixes.
