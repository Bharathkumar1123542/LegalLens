# LegalLens

GenAI-powered web application that helps non-lawyers understand, compare, and act on legal documents — without generating legal advice or replacing a licensed attorney.

> **Not legal advice.** LegalLens provides general information about your documents. Always consult a qualified attorney before acting on anything presented here.

---

## What it does (MVP)

| Capability | Detail |
|---|---|
| Upload | PDF, DOCX, TXT · ≤ 20 MB · ≤ 5 docs per comparison job |
| Simplification | Plain-language rewrite (elementary / plain English / detailed) |
| Clause & risk extraction | 10 clause types · 3-level risk rating with rationale |
| Comparison | Clause-aligned diff across 2–5 docs · materiality rating per difference |
| Q&A | Document-grounded chat · every answer cites a source passage |
| Export | Summary / action checklist / lawyer-prep brief → PDF, DOCX, or Markdown |

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose)
- Git
- (For local dev without Docker) Python 3.11+, Node.js 20+

## Quickstart (Docker Compose)

```bash
git clone <repo-url> legallens
cd legallens

# 1. Copy and fill in your API keys
cp .env.example .env
#    Edit .env: set ANTHROPIC_API_KEY, VOYAGE_API_KEY, JWT_SECRET

# 2. Start all services
docker compose -f infra/docker-compose.yml up --build

# 3. Verify
curl http://localhost:8000/health   # → {"status":"ok","environment":"development"}
open http://localhost:3000          # → LegalLens home page
```

## Local dev (no Docker)

### Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Postgres + Redis + MinIO must be running (use the compose stack for just the infra):
# docker compose -f infra/docker-compose.yml up postgres redis minio minio-init

cp ../../.env.example ../../.env  # then fill in values
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# → http://localhost:3000
```

## Running tests

```bash
# Backend (from apps/api/)
pytest tests/ -v

# Frontend (from apps/web/)
npm test
```

## Project structure

```
legallens/
├── .context/           # Source-of-truth context files (read before building)
├── apps/
│   ├── api/            # FastAPI backend (Python 3.11)
│   └── web/            # Next.js 14 frontend (TypeScript)
├── infra/
│   └── docker-compose.yml
├── .env.example        # All required environment variables documented
└── README.md
```

See [`.context/architecture.md`](.context/architecture.md) for the full system design.

## Implementation phases

| Phase | Scope | Status |
|---|---|---|
| 0 — Scaffolding | Repo structure, Docker Compose, CI, health endpoint | ✅ Complete |
| 1 — Auth & upload | Register/login, document upload through `status=uploaded` | ✅ Complete |
| 2 — Parsing, chunking, embeddings | Text extraction, OCR, chunking, Voyage AI embeddings | ✅ Complete |
| 3 — Simplification & clause extraction | LLM orchestration, `/simplify`, `/extract-clauses` | ✅ Complete |
| 4 — Document Q&A | RAG chat with citations | ✅ Complete |
| 5 — Comparison & export | Comparison engine, export to PDF/DOCX/MD | ✅ Complete |
| 6 — Missing features | Celery workers, PDF/DOCX renderers, Docker automation | ✅ Complete |
| 7 — Testing & quality | 80% coverage, golden dataset, LLM evaluation, performance tests | ✅ Complete |
| 8 — Deployment & CI/CD | GitHub Actions, rate limiting, file validation, staging/prod workflows | ✅ Complete |
| 9 — Security enhancements | MFA (TOTP), account lockout, CAPTCHA, CSP headers | ✅ Complete |

## Problem Statement Alignment

LegalLens addresses all seven use cases from the challenge problem statement:

| Use Case | Implementation | Endpoints / Services |
|---|---|---|
| **Simplifying complex legal documents** | Plain-language rewriting with 3 reading levels (elementary, plain English, detailed) using Claude Sonnet-4 with map-reduce for long docs | `POST /documents/{id}/simplify` → `services/simplification.py` |
| **Comparing contracts, agreements, or policies** | Clause-aligned comparison across 2–5 documents with materiality ratings (none/minor/significant/critical) | `POST /comparisons`, `GET /comparisons/{id}` → `services/comparison.py` |
| **Highlighting important clauses, obligations, risks** | 10 clause types extracted (indemnification, termination, liability, confidentiality, non-compete, arbitration, payment, auto-renewal, governing law, other) with 3-level risk rating (low/medium/high) + rationale | `POST /documents/{id}/extract-clauses`, `GET /documents/{id}/clauses` → `services/clause_extraction.py` |
| **Highlighting inconsistencies** | Comparison engine aligns same-type clauses across documents and generates diff summaries highlighting material differences | `GET /comparisons/{id}` (returns `diff_summary` per clause group) |
| **Answering questions based on provided legal documents** | RAG-powered chat with top-k semantic retrieval, conversation history, mandatory citations to source chunks | `POST /chat/sessions/{id}/messages` → `services/chat.py`, `services/llm_orchestration.py` |
| **Helping users understand their options and potential next steps** | Export types include "action checklist" (concrete next steps) and "lawyer preparation brief" (questions to ask an attorney) | `POST /exports` with `export_type=checklist` or `lawyer_brief` |
| **Generating summaries, checklists, or other actionable outputs** | Four export types (summary, checklist, lawyer brief, comparison report) in three formats (PDF, DOCX, Markdown) with structured sections and risk prioritization | `POST /exports`, `GET /exports/{id}` → `services/export.py`, `services/renderers/` |

**All endpoints documented**: See auto-generated API docs at `/docs` (Swagger UI) or `/redoc`.

**Citation requirement**: Every assistant answer in chat includes ≥1 citation with `chunk_id`, `page_number`, and `excerpt` for source traceability.

**Legal disclaimer**: All responses include "This is general information, not legal advice" per `architecture.md` §7.2.

For detailed architecture and data flow, see [`.context/architecture.md`](.context/architecture.md) and [`implementation_plan.md`](implementation_plan.md).

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, TanStack Query |
| Backend | Python 3.11, FastAPI, Celery, SQLAlchemy (async) |
| Database | PostgreSQL 15 + pgvector |
| Object storage | AWS S3 (prod) / MinIO (local dev) |
| LLM | Anthropic Claude (`claude-sonnet-5` / `claude-haiku-4-5-20251001`) |
| Embeddings | Voyage AI (`voyage-context-4`) |
| Cache / broker | Redis |

## Security note

- Files validated by **magic-byte inspection**, not extension
- Passwords hashed with **argon2id** — never stored or logged in plaintext
- JWT access tokens expire in 15 minutes; refresh tokens in 14 days
- Every document upload, export, deletion, and LLM call writes an immutable audit log row
- `audit_logs` table has **no UPDATE/DELETE grant** at the DB role level

## Open questions (not yet resolved — see `.context/progress-tracker.md`)

- Which jurisdiction(s) to target for clause heuristics at launch?
- Final data retention policy (30-day placeholder is unconfirmed)
- Malware scan: synchronous block vs. async quarantine?
- Pre-send PII redaction before content reaches Anthropic/Voyage AI?
- **UI design system**: no brand tokens defined — current colors are placeholders
