# AI Workflow Rules — LegalLens

> Governs: development workflow, scoping rules, delivery approach.
> Source: bootstrapped from `docs/implementation.md` v1.0 Section 8, plus
> the project's read-first operating rules.

## Operating rules (every session)

1. Read `project-overview.md`, `architecture.md`, `ui-context.md`,
   `code-standards.md`, `ai-workflow-rules.md` (this file), then
   `progress-tracker.md`, in that order, before writing code or making an
   architectural decision.
2. Identify the current phase from `progress-tracker.md` before deciding
   what to build. Never infer that a feature is in scope for "now" unless
   the current phase row below says so.
3. If anything is ambiguous or conflicts across files, surface it
   explicitly and propose a resolution before proceeding — do not resolve
   by assumption. (Live example: see the design-system gap flagged in
   `ui-context.md`.)
4. Implement only what the current phase permits. Do not pull work forward
   from a later phase, and do not add "nice to have" features not listed
   in `project-overview.md`'s in-scope table.
5. If an implementation changes something documented — scope, architecture,
   a standard, a UI convention — update the relevant context file **before**
   continuing, not after. Code must never diverge from docs silently.
6. After every meaningful change (code committed, architectural decision
   made, context file updated, open question resolved/added), update
   `progress-tracker.md`: what was completed, phase/milestone status, new
   open questions, and a next step specific enough for a fresh session to
   pick up without re-deriving context.
7. Ship the smallest working unit that advances the current phase. Don't
   bundle unrelated work into one change.

## Implementation Phases

Phases 0–5 constitute a demoable MVP buildable in a 48-hour hackathon
window; Phases 6–8 are production-hardening work that follows once the MVP
is validated. **Do not start a Phase 6+ task while Phase 0–5 exit criteria
are still unmet, and do not start Phase N+1 work before Phase N's exit
criteria are met**, except where explicitly parallelizable per the
Dependencies column.

| Phase | Scope | Dependencies | Deliverables | Exit criteria | Est. duration |
|---|---|---|---|---|---|
| 0 — Scaffolding | Repo structure, Docker Compose (Postgres+pgvector, Redis, MinIO), CI skeleton (lint+test on push) | None | Running local stack; empty FastAPI + Next.js apps talking to each other | `docker compose up` succeeds; health-check endpoint returns 200 | 3 h |
| 1 — Auth & upload | Auth Module, Document Ingestion Module (no OCR yet), S3/MinIO wiring | Phase 0 | Register/login; upload PDF/DOCX/TXT; `Document` row with status transitions | User can register, log in, and see an upload reach `status=uploaded` | 6 h |
| 2 — Parsing, chunking, embeddings | Text extraction, OCR fallback, chunking, Embedding Module via Voyage AI | Phase 1 | `document_chunks` populated with text + embeddings; `status` reaches `ready` | 10-page PDF reaches `status=ready` with correctly ordered, non-overlapping chunks | 6 h |
| 3 — Simplification & clause extraction | LLM Orchestration, Clause & Risk Extraction, `/simplify` + `/extract-clauses` | Phase 2 | Working simplification + clause/risk output on a real contract | Simplification streamed to client; ≥8/10 clause types correctly identified on a manual test doc | 8 h |
| 4 — Document Q&A | Conversational Q&A Module, RAG chat endpoints | Phase 2 (retrieval), Phase 3 (orchestration reused) | Working chat with citations in the UI | Every assistant answer in manual testing includes ≥1 citation resolvable to a real page/excerpt | 6 h |
| 5 — Comparison & export | Comparison Engine, Export Module, `/comparisons` + `/exports`, minimal comparison UI | Phase 3 (clause extraction reused) | Two-doc comparison with materiality ratings; PDF/Markdown export | 2-doc comparison produces ≥1 correctly identified significant/critical diff on a manual test pair; exports open correctly | 8 h |
| 6 — Security hardening | Rate limiting, magic-byte validation, malware scanning, audit logging, ownership checks on every endpoint | Phases 1–5 | All endpoints enforce ownership + rate limits; `audit_logs` populated for every state change | Automated suite confirms a user cannot access another user's documents via any endpoint | 1–2 days |
| 7 — Testing & evaluation | Full unit/integration/E2E suite, golden-dataset LLM eval harness | Phases 1–6 | CI gate on coverage + eval thresholds | CI blocks merges below 80% backend coverage or below success-criteria thresholds | 2–3 days |
| 8 — Deployment & scaling | Prod infra (ECS/K8s), autoscaling, monitoring dashboards, load testing | Phase 7 | Staging + prod environments; Grafana dashboards; load-test report | System meets p95 latency targets under 50 simulated concurrent users | 2–3 days |

## Assumptions currently in force (from the source spec — not yet confirmed
product decisions; do not silently harden these into permanent behavior)

- English-language documents only for the MVP.
- Individual users, not law-firm teams; no cross-user document sharing.
- No live attorney marketplace/booking integration; the "lawyer-prep
  brief" export is a standalone document.
- Anthropic's and Voyage AI's API terms permit sending user-uploaded
  document content as described — **must be confirmed against each
  provider's current terms (and a DPA if required) before handling real
  users' documents in production.**
- Default retention: 30 days from last access unless the user takes an
  explicit keep action — this is a placeholder pending a final
  product/legal decision (tracked in `progress-tracker.md`).
