# CLAUDE.md

Project instructions for Claude Code working in this repository (LegalLens — GenAI legal document assistant). Read this file before making any change. The full system design — architecture, data models, API contracts, phased build order — lives in `docs/implementation.md`; read the relevant section there before touching an area you don't already understand.

## Project Overview

LegalLens helps a non-lawyer understand, compare, and act on legal documents (contracts, leases, terms of service, policies) they already have. Core flows: plain-language simplification, clause/risk extraction, multi-document comparison, document-grounded Q&A with mandatory citations, and export (summary, checklist, lawyer-prep brief).

**LegalLens never gives legal advice.** It provides information, not counsel. Every user-facing output that touches document content MUST carry the "general information, not legal advice" disclaimer. Never remove this disclaimer or make it dismissible.

## Tech Stack

- Frontend: Next.js 14+, React 18+, TypeScript, Tailwind CSS, TanStack Query
- Backend: Python 3.11+, FastAPI (async), Celery + Redis for background jobs
- Data: PostgreSQL 15+ with the pgvector extension, S3-compatible object storage (MinIO locally)
- Generation: Anthropic Claude API — `claude-sonnet-5` for simplification/comparison/Q&A, `claude-haiku-4-5-20251001` for lightweight clause-type classification
- Embeddings: Voyage AI API, model `voyage-context-4` — Claude has no native embeddings endpoint; never attempt to call one for embeddings

Full rationale for every choice above: `docs/implementation.md` Section 3.

## Repository Layout

```
apps/web/src/            Next.js frontend (app router, components, hooks, lib, types)
apps/api/app/
  api/v1/                route handlers ONLY — no business logic here
  services/              all business logic lives here
  models/                SQLAlchemy ORM models
  schemas/                Pydantic request/response schemas
  workers/               Celery task definitions
  prompts/               versioned prompt templates
  db/                    session/engine setup
apps/api/tests/
  unit/  integration/  eval/     eval/ holds the golden-dataset LLM quality harness
apps/api/alembic/        database migrations
infra/                   docker-compose.yml, k8s manifests
docs/implementation.md   full system spec — read before any non-trivial change
```

## Commands

Treat these as the intended commands for this stack; verify against the actual `package.json` / `pyproject.toml` once they exist, and keep this section in sync as the project is scaffolded (Phase 0 in `docs/implementation.md`).

- Local stack: `docker compose -f infra/docker-compose.yml up`
- Backend dev server: `cd apps/api && uvicorn app.main:app --reload`
- Backend tests: `cd apps/api && pytest tests/unit tests/integration`
- Backend lint: `cd apps/api && ruff check app`
- Frontend dev server: `cd apps/web && npm run dev`
- Frontend tests: `cd apps/web && npm test`
- New migration: `cd apps/api && alembic revision --autogenerate -m "<message>"`, then `alembic upgrade head`

## Conventions

| Context | Convention | Example |
|---|---|---|
| REST API paths | kebab-case, plural nouns, versioned | `/api/v1/documents/{document_id}/extract-clauses` |
| Database tables/columns | snake_case | `document_chunks`, `risk_level` |
| Python identifiers | snake_case functions/variables, PascalCase classes | `generate_embeddings()`, `class ComparisonResult` |
| TypeScript identifiers | camelCase variables/functions, PascalCase components/types | `useDocumentStatus()`, `type ChatMessage` |
| Environment variables | UPPER_SNAKE_CASE | `ANTHROPIC_API_KEY` |
| Stored enum values | snake_case | `limitation_of_liability` |

`clause_type` is a fixed enum: `indemnification`, `termination`, `limitation_of_liability`, `confidentiality`, `non_compete`, `arbitration_dispute_resolution`, `payment_terms`, `auto_renewal`, `governing_law`, `other`.

## Non-Negotiable Rules

- All business logic MUST live in `app/services/`. Route handlers in `app/api/v1/` stay thin: validation and delegation only.
- Every call to the Claude or Voyage AI API MUST go through `app/services/llm_orchestration.py` or `app/services/embedding.py`. Never call either provider directly from a route handler or a worker task.
- Every assistant-generated claim about document content MUST carry a citation resolvable to a real `chunk_id`/`page_number`. If a response fails citation validation, regenerate once with stricter grounding; if it fails again, return "insufficient information in this document" — never return an uncited factual claim.
- Every state-changing action (upload, export, delete, LLM call) MUST write an `audit_logs` row (Section 5.9 of the implementation doc). The application's database role has no `UPDATE`/`DELETE` grant on that table — do not add one.
- Never log or persist a raw JWT secret, API key, or plaintext password.
- Never widen or rename a `clause_type` value without updating the golden evaluation set in `apps/api/tests/eval/` in the same change.

## Stop and Ask Before

- Adding a new third-party dependency, SDK, or API integration.
- Changing the database schema — confirm the migration is additive/backward-compatible unless told otherwise.
- Deleting any file outside the directory you were explicitly asked to work in.
- Modifying `.env`, `.env.example`, `.github/workflows/`, or anything under `infra/`.
- Removing or altering the "not legal advice" disclaimer anywhere it appears.

## Testing Expectations

- Backend service layer (`app/services/`): ≥ 80% line coverage, CI-enforced.
- Auth, file validation, and ownership-check paths: 100% coverage, CI-enforced, non-waivable.
- A prompt template change under `app/prompts/` is not done until it has been run against `apps/api/tests/eval/` without regressing the metrics in `docs/implementation.md` Section 1.4 (clause-extraction precision/recall, Q&A citation validity, readability delta).

## Do Not

- Do not add features, refactors, or files beyond what was explicitly asked for in a given task.
- Do not send document content to any LLM or embeddings provider other than Anthropic Claude and Voyage AI without an explicit instruction to do so.
- Do not fabricate a clause classification or answer when the source text is ambiguous — surface it as low-confidence or "insufficient information" instead (see `docs/implementation.md` Section 10 for the exact fallback behavior per failure mode).
