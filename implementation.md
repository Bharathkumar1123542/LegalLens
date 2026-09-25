# LegalLens — Implementation Specification

**Category:** AI for Legal Assistance & Access
**Document status:** v1.0 — single source of truth for implementation
**Audience:** engineers building, reviewing, or extending the system

---

## 1. Project Overview

### 1.1 Problem Statement

Non-lawyers routinely sign contracts, leases, terms of service, and policies they do not fully understand, because the documents are long, written in dense legal register, and expensive to have reviewed by a professional. LegalLens is a GenAI-powered web application that helps a non-lawyer understand, compare, and act on legal documents they already have — without generating legal advice or replacing a licensed attorney.

### 1.2 Purpose

LegalLens ingests one or more legal documents (contracts, agreements, policies, leases, offer letters, terms of service) and provides:

- Plain-language simplification of the full document or selected clauses.
- Extraction and risk-flagging of the clauses that matter (obligations, liabilities, termination conditions, auto-renewals, etc.).
- Side-by-side comparison of two or more documents, ranked by how materially they differ.
- Document-grounded question answering, with every answer traceable to a specific passage in the source document.
- Exportable artifacts a user can act on: a plain-language summary, an action checklist, and a "questions for your lawyer" brief.

### 1.3 Scope

**In scope (MVP):**

| Capability | Boundary |
|---|---|
| Document upload | PDF, DOCX, TXT; ≤ 20 MB per file; ≤ 5 documents per comparison job |
| Language | English-language source documents only |
| Simplification | Full-document and per-clause plain-language rewrite, selectable reading level |
| Clause & risk extraction | 10 predefined clause categories (Section 6.2), 3-level risk rating |
| Comparison | Clause-aligned diff across 2–5 documents with a materiality rating per difference |
| Q&A | Document-grounded chat with mandatory source citation per answer |
| Export | Summary, action checklist, and lawyer-prep brief, each as PDF, DOCX, or Markdown |
| Accounts | Single-tenant, individual user accounts (no team/workspace sharing) |

**Explicitly out of scope for this version:**

- Generating legal advice, legal opinions, or predictions of case outcomes.
- E-signature, contract execution, or redlining/negotiation workflows.
- Multi-language document support.
- Team workspaces, matter management, or multi-user collaboration on one document.
- Referral or booking integration with a live attorney or law firm.
- Jurisdiction-certified accuracy guarantees (the system is jurisdiction-aware where possible but does not warrant compliance with any specific jurisdiction's law).

### 1.4 Success Criteria

Success is measured against a fixed evaluation set (50 human-annotated legal documents spanning contracts, leases, and ToS documents, held out from any prompt-tuning work):

| Metric | Target | Measurement method |
|---|---|---|
| Readability improvement | Simplified output scores ≥ 4 grade levels lower on Flesch-Kincaid Grade Level than the source text | Automated scoring on a 20-document benchmark subset |
| Clause extraction precision | ≥ 0.85 | Compared against human-annotated clause spans and types on the 50-document gold set |
| Clause extraction recall | ≥ 0.80 | Same gold set |
| Q&A groundedness | ≥ 95% of answers cite a verifiable source chunk; 0% fabricated citations | Automated citation-validity check + manual spot audit of 10% of eval answers |
| Simplification latency | p95 ≤ 15 s for documents ≤ 20 pages, measured after ingestion completes | Load test against staging environment |
| Chat response latency | p95 ≤ 5 s per turn | Load test against staging environment |
| Ingestion success rate | ≥ 99% for supported file types under 20 MB | Production telemetry over a rolling 30-day window |
| Usability | ≥ 80% unassisted task completion across the three primary flows (simplify, compare, ask-a-question) | Moderated usability test, minimum 5 participants |

---

## 2. System Architecture

### 2.1 Components

| # | Component | Responsibility |
|---|---|---|
| 1 | Web Client (Next.js) | Upload UI, chat interface, comparison view, export controls |
| 2 | API Gateway / BFF (FastAPI) | AuthN/AuthZ enforcement, request validation, routing, rate limiting |
| 3 | Auth Service | Registration, login, token issuance and refresh |
| 4 | Ingestion Service | File validation, malware scan, text extraction, OCR fallback, chunking |
| 5 | Embedding Service | Generates chunk-level vector embeddings via Voyage AI, writes to pgvector |
| 6 | LLM Orchestration Service | Prompt construction, retrieval-augmented generation, calls to Claude, citation mapping |
| 7 | Clause & Risk Extraction Service | Hybrid rule-based + LLM clause tagging and risk scoring |
| 8 | Comparison Engine | Clause-level alignment and diffing across document sets |
| 9 | Export Service | Renders summary / checklist / lawyer-brief artifacts to PDF, DOCX, or Markdown |
| 10 | Job Queue (Celery + Redis) | Asynchronous execution of ingestion, embedding, extraction, comparison, export |
| 11 | Data Layer | PostgreSQL + pgvector, S3-compatible object storage, Redis cache |
| 12 | Audit & Observability | Structured logging, immutable audit trail, metrics, tracing, error monitoring |
| 13 | External Provider — Generation | Anthropic Claude API |
| 14 | External Provider — Embeddings | Voyage AI API |

### 2.2 Architecture Diagram

```mermaid
flowchart LR
    subgraph Client
        WEB[Web App - Next.js]
    end

    subgraph API["API Layer (FastAPI)"]
        GATEWAY[API Gateway / BFF]
        AUTH[Auth Service]
    end

    subgraph Workers["Async Workers (Celery)"]
        INGEST[Ingestion Service]
        EMBED[Embedding Service]
        CLAUSE[Clause and Risk Extraction]
        COMPARE[Comparison Engine]
        EXPORT[Export Service]
    end

    subgraph Orchestration
        LLM_ORCH[LLM Orchestration Service]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL and pgvector)]
        S3[(Object Storage - S3)]
        REDIS[(Redis: cache and broker)]
    end

    CLAUDE[Anthropic Claude API]
    VOYAGE[Voyage AI Embeddings API]

    WEB -->|HTTPS JSON| GATEWAY
    GATEWAY --> AUTH
    GATEWAY -->|enqueue job| REDIS
    REDIS --> INGEST
    INGEST -->|raw file| S3
    INGEST -->|extracted text| PG
    INGEST -->|enqueue| EMBED
    EMBED -->|embed request| VOYAGE
    VOYAGE -->|vectors| EMBED
    EMBED -->|chunk vectors| PG
    GATEWAY -->|sync request| LLM_ORCH
    LLM_ORCH -->|retrieve top-k chunks| PG
    LLM_ORCH -->|generation request| CLAUDE
    CLAUDE -->|completion| LLM_ORCH
    LLM_ORCH -->|persist message or result| PG
    REDIS --> CLAUSE
    CLAUSE -->|classification calls| CLAUDE
    CLAUSE -->|clause records| PG
    REDIS --> COMPARE
    COMPARE -->|diff generation calls| CLAUDE
    COMPARE -->|comparison result| PG
    REDIS --> EXPORT
    EXPORT -->|read structured data| PG
    EXPORT -->|write artifact| S3
    GATEWAY -->|poll status or fetch result| PG
    GATEWAY -->|signed download link| S3
    GATEWAY <-->|session and rate-limit state| REDIS
```

### 2.3 Data Flow

1. **Upload (sync).** Client sends a multipart upload to `POST /documents`. The gateway authenticates the request, validates MIME type and size, computes a SHA-256 hash for deduplication, stores the raw file in S3, creates a `Document` row with `status = uploaded`, enqueues an ingestion job, and returns `202 Accepted` with `document_id` and a status URL.
2. **Ingestion (async).** A worker fetches the file from S3, extracts text (PyMuPDF for PDF, python-docx for DOCX), and falls back to OCR (Tesseract) for any page with no extractable text layer. The worker chunks the text (~500 tokens per chunk, 50-token overlap) and writes rows to `document_chunks`. `Document.status` moves to `processing` on start and `ready` or `failed` on completion, with `processing_stage` tracking `extracting_text → ocr → chunking → embedding`.
3. **Embedding (async, chained).** A worker sends each chunk to the Voyage AI embeddings API and writes the returned vector into the `embedding` column (pgvector) on `document_chunks`.
4. **Feature request (sync from the client's perspective).** Once `Document.status = ready`, the client may request simplification, clause extraction, comparison, or chat. The gateway routes generation-heavy requests to the LLM Orchestration Service.
5. **Retrieval.** For chat, the orchestration service retrieves the top-k chunks by cosine similarity against the question's embedding. For full-document simplification, it processes all chunks in a map-reduce pattern (per-chunk simplification, then a final coherence pass).
6. **Generation.** The orchestration service constructs a prompt that embeds the retrieved chunks, an explicit citation requirement, and the system-level "informational, not legal advice" directive, then calls the Claude API (streaming enabled for chat and simplification). The response is parsed to map any cited claim back to a `chunk_id` and `page_number`.
7. **Persistence and response.** Results are persisted (`chat_messages`, `clauses`, or the relevant result table) and returned to the client with citation metadata for source highlighting in the UI.
8. **Comparison (async).** Triggered by `POST /comparisons` with 2–5 `document_ids`. The comparison engine aligns clauses by `clause_type` across the input documents (using prior clause-extraction output), calls Claude to produce a diff summary and materiality rating per aligned clause group, and persists `comparison_results` rows.
9. **Export (async).** Triggered by `POST /documents/{document_id}/export`. The export service assembles the requested artifact from already-persisted structured data — it does not re-call the LLM when cached extraction/simplification data is sufficient — renders it to the requested file format, uploads it to S3, and returns a signed, time-limited download URL.
10. **Audit.** Every state-changing action (upload, export, delete, and every LLM call) writes an `audit_logs` row recording the actor, action, resource, timestamp, and IP address.

---

## 3. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend framework | Next.js 14+ (React 18+, TypeScript) | App Router gives file-based routing for the four primary views (upload, document detail, comparison, chat); TypeScript enforces the same request/response shapes as the backend's Pydantic schemas, reducing integration bugs around document and clause data structures |
| Frontend styling | Tailwind CSS | Utility-first styling keeps the comparison/diff UI (which needs many small conditional styles for risk levels and diff highlighting) maintainable without a proliferation of one-off CSS files |
| Frontend server-state | TanStack Query | The UI is dominated by server-owned, asynchronous state (job status polling, chat history, comparison results); TanStack Query's caching and polling primitives fit this better than a general client-state library |
| Backend framework | Python 3.11+, FastAPI | Async-native, so I/O-bound LLM and embedding calls do not block the event loop; Pydantic request/response validation matches the strict schema requirements of legal document data; automatic OpenAPI generation keeps the contract in Section 7 in sync with the running service |
| Background jobs | Celery + Redis broker | Ingestion, OCR, embedding, comparison, and export are all long-running (seconds to low minutes) and must not block the request/response cycle; Celery is the mature, well-documented choice for Python async task execution |
| Relational database | PostgreSQL 15+ | ACID guarantees for user, document, and audit records; native JSONB for flexible metadata (e.g., chat citations) without a schema migration per new field |
| Vector store | pgvector extension on the same PostgreSQL instance | Avoids operating a second database engine for a hackathon-to-early-production scale system; keeps relational metadata and vector similarity search transactionally consistent (e.g., a chunk and its embedding are written in one flow); can be replaced by a dedicated vector database (Weaviate, Pinecone) if query volume outgrows a single Postgres instance |
| Object storage | S3-compatible storage (AWS S3 in production, MinIO for local development) | Durable, cheap, standard for storing raw uploaded files and generated export artifacts; supports server-side encryption at rest and signed URLs for time-limited downloads |
| Cache / rate limiting | Redis | Session token blocklists, per-user/per-IP rate-limit counters, and the Celery broker share the same Redis instance to minimize operational surface area |
| Document parsing | PyMuPDF (PDF), python-docx (DOCX) | Mature, actively maintained libraries with no per-call cost, avoiding a third-party parsing API dependency for the ingestion hot path |
| OCR | Tesseract OCR | Open-source, self-hostable fallback for scanned/image-only PDF pages, avoiding a per-page OCR API cost for the common case of digitally-native documents |
| LLM — generation | Anthropic Claude API, model `claude-sonnet-5` | Used for simplification, comparison diff summaries, and Q&A synthesis, where instruction-following quality and long-context handling of a full legal document matter most |
| LLM — lightweight classification | Anthropic Claude API, model `claude-haiku-4-5-20251001` | Used for high-volume, low-complexity calls (per-chunk clause-type pre-filtering) where a smaller, faster, cheaper model is sufficient and materially reduces per-document cost and latency |
| Embeddings | Voyage AI API, model `voyage-context-4` | Anthropic's Claude API does not provide a first-party embeddings endpoint and its own documentation directs developers to Voyage AI as the recommended embeddings partner; `voyage-context-4` produces contextualized chunk-level embeddings that retain full-document context without manual metadata augmentation, which is well suited to legal clauses whose meaning often depends on surrounding contract context |
| Auth | JWT (access + refresh tokens), argon2id password hashing | Stateless token verification scales horizontally without a session store on the auth-check hot path; argon2id is the current recommended password hashing algorithm |
| Containerization | Docker, Docker Compose (local), container orchestration (ECS Fargate or Kubernetes) in production | Standard portability guarantee between local development and production; Fargate avoids node management for a team without dedicated infrastructure staff |
| CI/CD | GitHub Actions | Tight integration with the source repository; sufficient for the team size and release cadence of this project without adopting a separate CI platform |
| Monitoring | Prometheus + Grafana (metrics), Sentry (error tracking), structured JSON logs shipped to a log aggregator | LLM pipelines fail in ways that are hard to reproduce locally (partial responses, rate limits, malformed citations); structured logs and error tracking are required to debug production incidents from telemetry alone |

### 3.1 Naming Conventions

| Context | Convention | Example |
|---|---|---|
| REST API paths | kebab-case, plural nouns, versioned | `/api/v1/documents/{document_id}/extract-clauses` |
| Database tables/columns | snake_case, singular table names avoided in favor of plural | `document_chunks`, `risk_level` |
| Python identifiers | snake_case for functions/variables, PascalCase for classes | `generate_embeddings()`, `class ComparisonResult` |
| TypeScript identifiers | camelCase for variables/functions, PascalCase for components/types | `useDocumentStatus()`, `type ChatMessage` |
| Environment variables | UPPER_SNAKE_CASE | `ANTHROPIC_API_KEY` |
| Enum values (stored) | snake_case | `limitation_of_liability` |

---

## 4. Directory & File Structure

```
legallens/
├── apps/
│   ├── web/                          # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/                  # App Router pages (upload, document/[id], compare, chat)
│   │   │   ├── components/           # Reusable UI: DiffView, RiskBadge, ClauseCard, ChatPane
│   │   │   ├── hooks/                # useDocumentStatus, useChatSession, useComparison
│   │   │   ├── lib/                  # api client, auth token handling, formatting helpers
│   │   │   ├── styles/               # Tailwind config and global styles
│   │   │   └── types/                # TypeScript types mirrored from backend Pydantic schemas
│   │   ├── public/
│   │   ├── package.json
│   │   └── next.config.js
│   └── api/                          # FastAPI backend
│       ├── app/
│       │   ├── main.py               # FastAPI app instantiation, middleware registration
│       │   ├── core/                 # config.py (Pydantic Settings), security.py, logging.py
│       │   ├── api/v1/               # route modules: auth.py, documents.py, comparisons.py, chat.py, exports.py
│       │   ├── services/             # business logic: ingestion.py, embedding.py, llm_orchestration.py,
│       │   │                         #   clause_extraction.py, comparison.py, export.py, audit.py
│       │   ├── models/               # SQLAlchemy ORM models, one file per aggregate (user.py, document.py, ...)
│       │   ├── schemas/              # Pydantic request/response schemas, mirrors models/ 1:1 where applicable
│       │   ├── workers/              # Celery task definitions, one file per async job type
│       │   ├── prompts/              # versioned prompt templates (simplify.md, extract_clauses.md, compare.md, chat.md)
│       │   └── db/                   # session.py, base.py
│       ├── tests/
│       │   ├── unit/
│       │   ├── integration/
│       │   └── eval/                 # LLM-quality golden-dataset evaluation harness
│       ├── alembic/                  # database migrations
│       ├── requirements.txt
│       └── Dockerfile
├── infra/
│   ├── docker-compose.yml            # local dev: api, web, postgres+pgvector, redis, minio
│   └── k8s/                          # production manifests (post-MVP)
├── docs/
│   └── implementation.md             # this document
├── .github/workflows/                # ci.yml (lint, test), deploy.yml
├── .env.example
└── README.md
```

---

## 5. Core Modules

Each module is a Python package under `apps/api/app/services/`, exposed through the API layer in `apps/api/app/api/v1/`.

### 5.1 Auth Module

- **Responsibility:** user registration, login, token issuance, token refresh, password hashing and verification.
- **Inputs:** email, password (registration/login); refresh token (refresh flow).
- **Outputs:** `User` record; JWT access token (15-minute expiry) and refresh token (14-day expiry).
- **Interface:**
  ```python
  async def register_user(email: str, password: str, full_name: str) -> User: ...
  async def authenticate_user(email: str, password: str) -> TokenPair: ...
  async def refresh_access_token(refresh_token: str) -> TokenPair: ...
  ```

### 5.2 Document Ingestion Module

- **Responsibility:** validate uploaded files, store raw bytes, extract text, apply OCR where needed, chunk text.
- **Inputs:** `UploadFile`, `owner_id`.
- **Outputs:** `Document` record (`status = ready` or `failed`); `DocumentChunk` records.
- **Interface:**
  ```python
  async def create_document(owner_id: UUID, file: UploadFile) -> Document: ...
  async def process_document(document_id: UUID) -> None: ...  # Celery task entry point
  ```

### 5.3 Embedding & Retrieval Module

- **Responsibility:** generate chunk embeddings via Voyage AI; perform similarity search over `document_chunks` for a given query.
- **Inputs:** list of chunk texts (embedding generation); query text + `document_id` (retrieval).
- **Outputs:** vectors written to `document_chunks.embedding`; ranked list of chunks (retrieval).
- **Interface:**
  ```python
  async def embed_chunks(document_id: UUID) -> None: ...
  async def retrieve_relevant_chunks(
      document_id: UUID, query: str, top_k: int = 8
  ) -> list[DocumentChunk]: ...
  ```

### 5.4 LLM Orchestration Module

- **Responsibility:** construct grounded prompts (system directive + retrieved context + user request), call the Claude API, parse and validate citations in the response.
- **Inputs:** task type (`simplify`, `chat`, `extract_clauses`, `compare`), retrieved chunks, user input.
- **Outputs:** generated text with a citation list mapping claims to `chunk_id`/`page_number`.
- **Interface:**
  ```python
  async def generate_grounded_response(
      task: Literal["simplify", "chat", "extract_clauses", "compare"],
      context_chunks: list[DocumentChunk],
      user_input: str,
      reading_level: str | None = None,
  ) -> GroundedResponse: ...
  ```

### 5.5 Clause & Risk Extraction Module

- **Responsibility:** identify clause spans, classify each into one of the 10 clause types (Section 6.2), assign a risk level, and generate a one-sentence risk rationale.
- **Inputs:** `document_id`.
- **Outputs:** `Clause` records.
- **Interface:**
  ```python
  async def extract_clauses(document_id: UUID) -> list[Clause]: ...
  ```
- **Implementation note:** a regex/keyword pre-filter (e.g., "terminate", "indemnify", "auto-renew") narrows candidate chunks per clause type before the LLM classification call, reducing the number of `claude-haiku-4-5-20251001` calls per document.

### 5.6 Comparison Engine Module

- **Responsibility:** align clauses of the same type across 2–5 documents, generate a diff summary and materiality rating per aligned group.
- **Inputs:** `document_ids` (already processed and clause-extracted).
- **Outputs:** `ComparisonJob` and `ComparisonResult` records.
- **Interface:**
  ```python
  async def create_comparison(owner_id: UUID, document_ids: list[UUID]) -> ComparisonJob: ...
  async def run_comparison(comparison_job_id: UUID) -> None: ...  # Celery task entry point
  ```

### 5.7 Conversational Q&A (Chat) Module

- **Responsibility:** manage chat session lifecycle and turn-by-turn history; delegate generation to the LLM Orchestration Module.
- **Inputs:** `document_id`, optional `session_id`, `question`.
- **Outputs:** `ChatSession`, `ChatMessage` records with citations.
- **Interface:**
  ```python
  async def start_chat_session(document_id: UUID, owner_id: UUID) -> ChatSession: ...
  async def ask_question(
      document_id: UUID, session_id: UUID, question: str
  ) -> ChatMessage: ...
  ```

### 5.8 Export & Output Generation Module

- **Responsibility:** assemble a summary, checklist, or lawyer-prep brief from persisted structured data and render it to the requested file format.
- **Inputs:** `document_id` (or `comparison_job_id`), `export_type`, `file_format`.
- **Outputs:** `ExportArtifact` record; file written to S3.
- **Interface:**
  ```python
  async def generate_export(
      owner_id: UUID,
      export_type: Literal["summary", "checklist", "lawyer_brief", "comparison_report"],
      file_format: Literal["pdf", "docx", "md"],
      document_id: UUID | None = None,
      comparison_job_id: UUID | None = None,
  ) -> ExportArtifact: ...
  ```

### 5.9 Audit & Compliance Logging Module

- **Responsibility:** record every state-changing action and every LLM call for compliance and debugging.
- **Inputs:** actor, action, resource type/id, metadata.
- **Outputs:** `AuditLog` record (append-only).
- **Interface:**
  ```python
  async def record_audit_event(
      actor_id: UUID | None,
      action: str,
      resource_type: str,
      resource_id: UUID,
      metadata: dict,
      ip_address: str,
  ) -> None: ...
  ```

### 5.10 Async Job Coordination Module

- **Responsibility:** enqueue and track Celery task state; expose job status to the API layer for client polling.
- **Inputs:** job type, job payload.
- **Outputs:** job status transitions surfaced via `Document.status`, `ComparisonJob.status`, `ExportArtifact.status`.
- **Interface:**
  ```python
  def enqueue_job(job_type: str, payload: dict) -> str:  # returns Celery task id
      ...
  def get_job_status(task_id: str) -> JobStatus: ...
  ```

---

## 6. Data Models

### 6.1 Entity-Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ DOCUMENT : owns
    USER ||--o{ COMPARISON_JOB : requests
    USER ||--o{ CHAT_SESSION : owns
    USER ||--o{ EXPORT_ARTIFACT : requests
    DOCUMENT ||--o{ DOCUMENT_CHUNK : contains
    DOCUMENT ||--o{ CLAUSE : contains
    DOCUMENT ||--o{ CHAT_SESSION : scopes
    DOCUMENT }o--o{ COMPARISON_JOB : "included in"
    COMPARISON_JOB ||--o{ COMPARISON_RESULT : produces
    CHAT_SESSION ||--o{ CHAT_MESSAGE : contains
    DOCUMENT_CHUNK ||--o{ CLAUSE : "source of"
    DOCUMENT_CHUNK ||--o{ CHAT_MESSAGE : "cited by"
```

### 6.2 Schema Definitions

**`users`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `email` | varchar(255) | UNIQUE, NOT NULL |
| `password_hash` | varchar(255) | NOT NULL (argon2id) |
| `full_name` | varchar(255) | NOT NULL |
| `role` | enum(`user`, `admin`) | NOT NULL, default `user` |
| `is_active` | boolean | NOT NULL, default `true` |
| `created_at` | timestamptz | NOT NULL, default `now()` |
| `updated_at` | timestamptz | NOT NULL, default `now()` |

**`documents`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `owner_id` | UUID | FK → `users.id`, NOT NULL |
| `original_filename` | varchar(512) | NOT NULL |
| `mime_type` | varchar(128) | NOT NULL, one of `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain` |
| `file_size_bytes` | bigint | NOT NULL, ≤ 20,971,520 (20 MB) |
| `storage_key` | varchar(512) | NOT NULL, S3 object key |
| `file_hash_sha256` | char(64) | NOT NULL, indexed, used for per-user deduplication |
| `status` | enum(`uploaded`, `processing`, `ready`, `failed`) | NOT NULL, default `uploaded` |
| `processing_stage` | enum(`extracting_text`, `ocr`, `chunking`, `embedding`) | nullable, meaningful only while `status = processing` |
| `page_count` | integer | nullable |
| `language` | varchar(8) | nullable, BCP-47 tag, e.g. `en` |
| `failure_reason` | text | nullable, set when `status = failed` |
| `created_at` / `updated_at` | timestamptz | NOT NULL |

**`document_chunks`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `document_id` | UUID | FK → `documents.id`, NOT NULL |
| `chunk_index` | integer | NOT NULL, 0-based, unique per `document_id` |
| `page_number` | integer | nullable |
| `text` | text | NOT NULL, ≤ 500 tokens target length |
| `token_count` | integer | NOT NULL |
| `embedding` | vector(1024) | nullable until embedding step completes; dimension pinned to the selected Voyage AI model at integration time |
| `created_at` | timestamptz | NOT NULL |

**`clauses`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `document_id` | UUID | FK → `documents.id`, NOT NULL |
| `source_chunk_id` | UUID | FK → `document_chunks.id`, nullable |
| `clause_type` | enum (see below) | NOT NULL |
| `text_excerpt` | text | NOT NULL |
| `start_offset` | integer | NOT NULL, character offset within `source_chunk_id.text` |
| `end_offset` | integer | NOT NULL, > `start_offset` |
| `risk_level` | enum(`low`, `medium`, `high`) | NOT NULL |
| `risk_rationale` | text | NOT NULL, one to two sentences |
| `created_at` | timestamptz | NOT NULL |

`clause_type` enum values: `indemnification`, `termination`, `limitation_of_liability`, `confidentiality`, `non_compete`, `arbitration_dispute_resolution`, `payment_terms`, `auto_renewal`, `governing_law`, `other`.

**`comparison_jobs`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `owner_id` | UUID | FK → `users.id`, NOT NULL |
| `status` | enum(`queued`, `running`, `completed`, `failed`) | NOT NULL, default `queued` |
| `created_at` / `completed_at` | timestamptz | `completed_at` nullable until terminal state |

**`comparison_job_documents`** (join table)

| Column | Type | Constraints |
|---|---|---|
| `comparison_job_id` | UUID | FK → `comparison_jobs.id`, part of composite PK |
| `document_id` | UUID | FK → `documents.id`, part of composite PK |

Constraint: 2 ≤ number of rows per `comparison_job_id` ≤ 5, enforced at the service layer on job creation.

**`comparison_results`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `comparison_job_id` | UUID | FK → `comparison_jobs.id`, NOT NULL |
| `clause_type` | varchar(64) | NOT NULL |
| `excerpts_by_document` | jsonb | NOT NULL, `{document_id: excerpt_text}` |
| `diff_summary` | text | NOT NULL |
| `materiality` | enum(`none`, `minor`, `significant`, `critical`) | NOT NULL |
| `created_at` | timestamptz | NOT NULL |

**`chat_sessions`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `document_id` | UUID | FK → `documents.id`, NOT NULL |
| `owner_id` | UUID | FK → `users.id`, NOT NULL |
| `created_at` / `last_message_at` | timestamptz | NOT NULL |

**`chat_messages`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `session_id` | UUID | FK → `chat_sessions.id`, NOT NULL |
| `role` | enum(`user`, `assistant`) | NOT NULL |
| `content` | text | NOT NULL |
| `citations` | jsonb | NOT NULL, default `[]`; array of `{chunk_id, page_number, excerpt}`; required non-empty when `role = assistant` and the answer makes a factual claim about the document |
| `created_at` | timestamptz | NOT NULL |

**`export_artifacts`**

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `owner_id` | UUID | FK → `users.id`, NOT NULL |
| `document_id` | UUID | FK → `documents.id`, nullable (null for comparison exports) |
| `comparison_job_id` | UUID | FK → `comparison_jobs.id`, nullable (null for single-document exports) |
| `export_type` | enum(`summary`, `checklist`, `lawyer_brief`, `comparison_report`) | NOT NULL |
| `file_format` | enum(`pdf`, `docx`, `md`) | NOT NULL |
| `status` | enum(`queued`, `generating`, `ready`, `failed`) | NOT NULL, default `queued` |
| `storage_key` | varchar(512) | nullable until `status = ready` |
| `created_at` | timestamptz | NOT NULL |

Constraint: exactly one of `document_id`, `comparison_job_id` is non-null.

**`audit_logs`** (append-only, no UPDATE or DELETE grants at the database role level)

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `actor_id` | UUID | FK → `users.id`, nullable for system-initiated actions |
| `action` | varchar(64) | NOT NULL, e.g. `document.upload`, `document.export`, `document.delete`, `llm.call` |
| `resource_type` | varchar(64) | NOT NULL |
| `resource_id` | UUID | NOT NULL |
| `metadata` | jsonb | NOT NULL, default `{}` |
| `ip_address` | inet | NOT NULL |
| `created_at` | timestamptz | NOT NULL |

### 6.3 Validation Rules

- File uploads: MIME type validated by magic-byte inspection, not file extension; rejected outside the three supported types; rejected above 20 MB; rejected if `file_hash_sha256` already exists for the same `owner_id` (return the existing `Document` instead of re-processing).
- `document_chunks.text`: hard cap of 700 tokens per chunk (500 target + overlap tolerance); chunks that would exceed this are split at the nearest sentence boundary.
- `clauses.end_offset` must be strictly greater than `start_offset` and both must fall within the bounds of the referenced chunk's `text`.
- `chat_messages.citations`: an assistant message that makes any claim about document content must have at least one citation; a message with zero citations is only valid when it is a clarifying question or an explicit "insufficient information in this document" response.
- `comparison_job_documents`: rejected at creation if fewer than 2 or more than 5 `document_id` values are supplied, or if any referenced document has `status != ready`.
- All monetary or date values extracted into `clauses.text_excerpt` are stored as the original source text, never as a parsed/normalized value — normalization for display is a presentation-layer concern, not a data-integrity guarantee this system makes.

---

## 7. API / Interface Contracts

All endpoints are under `/api/v1`, require `Authorization: Bearer <access_token>` unless noted, and return `application/json` except export downloads.

### 7.1 REST Endpoints

| Method | Path | Purpose | Success | Key errors |
|---|---|---|---|---|
| POST | `/auth/register` | Create a user account | 201 | 400 validation, 409 email exists |
| POST | `/auth/login` | Exchange credentials for tokens | 200 | 401 invalid credentials |
| POST | `/auth/refresh` | Exchange refresh token for a new access token | 200 | 401 invalid/expired refresh token |
| POST | `/documents` | Upload a document | 202 | 400 invalid file, 413 too large |
| GET | `/documents/{document_id}` | Fetch document metadata | 200 | 404 not found, 403 not owner |
| GET | `/documents/{document_id}/status` | Poll ingestion status | 200 | 404 |
| DELETE | `/documents/{document_id}` | Hard-delete a document and its derived data | 204 | 404, 403 |
| POST | `/documents/{document_id}/simplify` | Generate a plain-language simplification | 200 (sync, streamed) | 409 document not ready, 502 LLM upstream error |
| POST | `/documents/{document_id}/extract-clauses` | Run clause and risk extraction | 202 (async) | 409 document not ready |
| GET | `/documents/{document_id}/clauses` | List extracted clauses | 200 | 404 |
| POST | `/comparisons` | Start a multi-document comparison job | 202 | 400 invalid document set |
| GET | `/comparisons/{comparison_job_id}` | Fetch comparison status/results | 200 | 404, 403 |
| POST | `/documents/{document_id}/chat/sessions` | Start a chat session | 201 | 409 document not ready |
| POST | `/documents/{document_id}/chat/sessions/{session_id}/messages` | Ask a question | 200 (streamed) | 409, 502 |
| GET | `/documents/{document_id}/chat/sessions/{session_id}/messages` | Fetch chat history | 200 | 404 |
| POST | `/exports` | Request an export artifact | 202 | 400, 409 source not ready |
| GET | `/exports/{export_id}` | Fetch export status / signed download URL | 200 | 404, 403 |

### 7.2 Selected Request/Response Schemas

**`POST /documents`** (multipart/form-data)

Request: `file` (binary, required)

Response `202`:
```json
{
  "document_id": "uuid",
  "status": "uploaded",
  "status_url": "/api/v1/documents/{document_id}/status"
}
```

**`POST /documents/{document_id}/simplify`**

Request:
```json
{
  "reading_level": "plain_english",
  "scope": "full_document"
}
```
`reading_level`: one of `elementary`, `plain_english`, `detailed` (default `plain_english`).
`scope`: one of `full_document`, `{"clause_id": "uuid"}`.

Response `200` (streamed as server-sent events, final event shown):
```json
{
  "simplified_text": "string",
  "citations": [
    {"chunk_id": "uuid", "page_number": 3, "excerpt": "string"}
  ],
  "disclaimer": "This is general information, not legal advice."
}
```

**`POST /documents/{document_id}/chat/sessions/{session_id}/messages`**

Request:
```json
{ "question": "string, 1-2000 characters" }
```

Response `200`:
```json
{
  "message_id": "uuid",
  "role": "assistant",
  "content": "string",
  "citations": [
    {"chunk_id": "uuid", "page_number": 5, "excerpt": "string"}
  ],
  "created_at": "ISO-8601 timestamp"
}
```

**`POST /comparisons`**

Request:
```json
{ "document_ids": ["uuid", "uuid"] }
```
Validation: 2 ≤ length ≤ 5; all documents must belong to the requesting user and have `status = ready`.

Response `202`:
```json
{ "comparison_job_id": "uuid", "status": "queued" }
```

**`GET /comparisons/{comparison_job_id}`**

Response `200`:
```json
{
  "comparison_job_id": "uuid",
  "status": "completed",
  "results": [
    {
      "clause_type": "termination",
      "excerpts_by_document": {"uuid-a": "string", "uuid-b": "string"},
      "diff_summary": "string",
      "materiality": "significant"
    }
  ]
}
```

**`POST /exports`**

Request:
```json
{
  "export_type": "lawyer_brief",
  "file_format": "pdf",
  "document_id": "uuid"
}
```
Exactly one of `document_id` or `comparison_job_id` must be present.

Response `202`:
```json
{ "export_id": "uuid", "status": "queued" }
```

### 7.3 Service-Layer Function Signatures

```python
# services/ingestion.py
async def create_document(owner_id: UUID, file: UploadFile) -> Document: ...
async def process_document(document_id: UUID) -> None: ...

# services/embedding.py
async def embed_chunks(document_id: UUID) -> None: ...
async def retrieve_relevant_chunks(
    document_id: UUID, query: str, top_k: int = 8
) -> list[DocumentChunk]: ...

# services/llm_orchestration.py
async def generate_grounded_response(
    task: Literal["simplify", "chat", "extract_clauses", "compare"],
    context_chunks: list[DocumentChunk],
    user_input: str,
    reading_level: str | None = None,
) -> GroundedResponse: ...

# services/clause_extraction.py
async def extract_clauses(document_id: UUID) -> list[Clause]: ...

# services/comparison.py
async def create_comparison(owner_id: UUID, document_ids: list[UUID]) -> ComparisonJob: ...
async def run_comparison(comparison_job_id: UUID) -> None: ...

# services/chat.py
async def start_chat_session(document_id: UUID, owner_id: UUID) -> ChatSession: ...
async def ask_question(document_id: UUID, session_id: UUID, question: str) -> ChatMessage: ...

# services/export.py
async def generate_export(
    owner_id: UUID,
    export_type: Literal["summary", "checklist", "lawyer_brief", "comparison_report"],
    file_format: Literal["pdf", "docx", "md"],
    document_id: UUID | None = None,
    comparison_job_id: UUID | None = None,
) -> ExportArtifact: ...

# services/audit.py
async def record_audit_event(
    actor_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: UUID,
    metadata: dict,
    ip_address: str,
) -> None: ...
```

---

## 8. Implementation Phases

Phases 0–5 constitute a demoable MVP buildable in a 48-hour hackathon window; Phases 6–8 are production-hardening work that follows once the MVP is validated.

| Phase | Scope | Dependencies | Deliverables | Exit criteria | Est. duration |
|---|---|---|---|---|---|
| 0 — Scaffolding | Repo structure, Docker Compose (Postgres+pgvector, Redis, MinIO), CI skeleton (lint + test on push) | None | Running local stack; empty FastAPI and Next.js apps talking to each other | `docker compose up` succeeds; health-check endpoint returns 200 | 3 h |
| 1 — Auth & upload | Auth Module (5.1), Document Ingestion Module (5.2) without OCR, S3/MinIO wiring | Phase 0 | Register/login; upload a PDF/DOCX/TXT; `Document` row created with `status` transitions | A user can register, log in, and see an uploaded document reach `status = uploaded` | 6 h |
| 2 — Parsing, chunking, embeddings | Text extraction, OCR fallback, chunking, Embedding Module (5.3) via Voyage AI | Phase 1 | `document_chunks` populated with text and embeddings; `status` reaches `ready` | A 10-page PDF reaches `status = ready` with correctly ordered, non-overlapping-content chunks | 6 h |
| 3 — Simplification & clause extraction | LLM Orchestration Module (5.4), Clause & Risk Extraction Module (5.5), `/simplify` and `/extract-clauses` endpoints | Phase 2 | Working simplification and clause/risk output on a real contract | Simplification output is streamed to the client; at least 8 of 10 clause types are correctly identified on a manual test document | 8 h |
| 4 — Document Q&A | Conversational Q&A Module (5.7), retrieval-augmented chat endpoints | Phase 2 (retrieval), Phase 3 (orchestration reused) | Working chat with citations rendered in the UI | Every assistant answer in manual testing includes at least one citation resolvable to a real page/excerpt | 6 h |
| 5 — Comparison & export | Comparison Engine (5.6), Export Module (5.8), `/comparisons` and `/exports` endpoints, minimal comparison UI | Phase 3 (clause extraction reused) | Two-document comparison with materiality ratings; PDF/Markdown export of summary and checklist | A 2-document comparison produces at least one correctly identified "significant" or "critical" difference on a manual test pair; export downloads open correctly | 8 h |
| 6 — Security hardening | Rate limiting, file magic-byte validation, malware scanning, audit logging (5.9), row-level ownership checks on every endpoint | Phases 1–5 | All endpoints enforce ownership and rate limits; `audit_logs` populated for every state change | Automated test suite confirms a user cannot access another user's documents via any endpoint | 1–2 days |
| 7 — Testing & evaluation | Full unit/integration/E2E suite (Section 11), golden-dataset LLM evaluation harness | Phases 1–6 | CI gate on the coverage and eval thresholds in Section 11 | CI blocks merges below 80% backend line coverage or below the Section 1.4 clause-extraction/groundedness thresholds | 2–3 days |
| 8 — Deployment & scaling | Production infrastructure (ECS/Kubernetes), autoscaling policy, monitoring dashboards, load testing against Section 13 targets | Phase 7 | Staging and production environments; Grafana dashboards; load-test report | System meets the p95 latency targets in Section 1.4 under a simulated load of 50 concurrent users | 2–3 days |

---

## 9. Configuration & Environment

| Variable | Required | Example | Notes |
|---|---|---|---|
| `ENVIRONMENT` | Yes | `development` | One of `development`, `staging`, `production` |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@localhost:5432/legallens` | Includes pgvector-enabled database |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Shared by cache, rate limiter, and Celery broker |
| `CELERY_BROKER_URL` | Yes | `redis://localhost:6379/1` | Separate Redis DB index from cache to avoid key collisions |
| `S3_BUCKET` | Yes | `legallens-documents` | |
| `S3_ENDPOINT_URL` | Local dev only | `http://localhost:9000` | Points at MinIO locally; omitted in production (uses AWS default) |
| `S3_ACCESS_KEY_ID` | Yes | — | Injected via secrets manager in production, never committed |
| `S3_SECRET_ACCESS_KEY` | Yes | — | Injected via secrets manager in production, never committed |
| `ANTHROPIC_API_KEY` | Yes | — | Injected via secrets manager in production |
| `VOYAGE_API_KEY` | Yes | — | Injected via secrets manager in production |
| `JWT_SECRET` | Yes | — | 256-bit random value, rotated on a defined schedule |
| `JWT_ALGORITHM` | Yes | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | `15` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Yes | `14` | |
| `MAX_UPLOAD_SIZE_MB` | Yes | `20` | Enforced at both the reverse proxy and the application layer |
| `ALLOWED_MIME_TYPES` | Yes | `application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain` | |
| `CORS_ORIGINS` | Yes | `https://app.legallens.example` | Comma-separated allow-list, never `*` in production |
| `RATE_LIMIT_PER_MINUTE` | Yes | `30` | Per-user limit on LLM-calling endpoints |
| `SENTRY_DSN` | Production only | — | |
| `LOG_LEVEL` | Yes | `INFO` | `DEBUG` in development only |

**Secrets management:** `.env` files are used for local development only and are excluded via `.gitignore`; `.env.example` documents every required variable with placeholder values. In staging and production, secrets are injected at deploy time from a managed secrets store (AWS Secrets Manager or equivalent) and are never baked into container images or logged. Configuration is loaded through a single `Settings` class (Pydantic `BaseSettings`) so that a missing required variable fails application startup immediately rather than failing on first use.

---

## 10. Error Handling & Edge Cases

| Failure mode | Detection | Mitigation / user-facing behavior |
|---|---|---|
| Unsupported file type | Magic-byte check at upload | `400` with a clear message listing supported types; file is not stored |
| Corrupted or unparseable file | Parser raises an exception during ingestion | `Document.status = failed`, `failure_reason` populated; client polling `/status` sees `failed` with a retry-with-a-different-file suggestion |
| Scanned/image-only PDF | No extractable text layer on a page | OCR fallback runs automatically; if OCR confidence is below threshold, the page is flagged as `low_confidence` in `processing_stage` metadata and included in the output with a visible caveat |
| Document exceeds size/page practical limits | Chunk count exceeds a configured ceiling (e.g., > 400 chunks) | Full-document simplification switches to a hierarchical map-reduce summarization pass instead of a single-pass prompt; client is informed the response may take longer |
| LLM API timeout, rate limit, or 5xx | Exception/timeout from the Claude or Voyage AI SDK call | Exponential backoff retry (up to 3 attempts); on final failure, `502` returned with a message distinguishing "temporary service issue" from a data problem; the triggering request is not silently dropped — it is logged for reprocessing |
| LLM hallucination / ungrounded claim | Post-generation citation validator finds a claim with no matching citation, or a citation pointing at a `chunk_id` not in the retrieved set | Response is rejected and regenerated once with a stricter grounding instruction; if the second attempt also fails validation, the system returns "insufficient information in this document to answer that" rather than an unverified answer |
| Ambiguous or genuinely conflicting clauses in comparison | Comparison prompt explicitly asks the model to flag ambiguity rather than resolve it | Result is tagged `materiality = critical` with a note that professional review is recommended, rather than the system asserting which version is "better" |
| Non-English document submitted | Language detection during ingestion returns non-`en` with high confidence | Upload is accepted, but the client is shown a warning that output quality is not validated for the detected language, and the `language` field is stored for future scoping |
| Duplicate upload | `file_hash_sha256` matches an existing document for the same owner | The existing `Document` is returned instead of creating a duplicate and re-processing |
| PII or highly sensitive content in a document | Not automatically detected in the MVP scope | User-facing disclosure at upload time stating that document content is sent to third-party LLM/embedding providers under their respective data-handling terms; a future phase may add a pre-send redaction option (Section 14) |
| Expired or invalid access token | JWT verification fails or token is past expiry | `401`; client uses the refresh token to obtain a new access token transparently, or is redirected to login if the refresh token has also expired |
| Partial failure in multi-document comparison | One document in the set has `status != ready` or fails during comparison processing | `400` at job creation if a document is not `ready`; if a mid-job failure occurs, `ComparisonJob.status = failed` with the specific failing `document_id` recorded, rather than returning a partial result that looks complete |

---

## 11. Testing Strategy

### 11.1 Unit Tests (pytest, Jest)

- Parsers: PDF/DOCX/TXT text extraction against a fixture set of known-good and known-corrupt files.
- Chunking: correct chunk boundaries, overlap, and token counting against fixed-length fixture texts.
- Schema validation: every Pydantic request/response schema rejects invalid payloads (missing fields, out-of-range values, wrong enum values).
- Clause regex pre-filter: correct candidate-chunk narrowing for each of the 10 clause types against labeled fixture text.
- Frontend: component-level tests for `DiffView`, `RiskBadge`, and citation-rendering components against fixed props.

### 11.2 Integration Tests

- Full ingestion pipeline: upload → parse → chunk → embed, asserting final `Document.status = ready` and a non-empty, correctly ordered `document_chunks` set.
- API contract tests (pytest + httpx) covering every endpoint in Section 7.1 for both success and documented error responses.
- LLM prompt/response contract tests using recorded response fixtures (cassette-style, no live API calls in CI) to verify prompt construction and response parsing logic independent of live model behavior.
- Ownership/authorization tests: a second user's token must receive `403`/`404` on every resource-scoped endpoint.

### 11.3 End-to-End Tests (Playwright)

- Upload a document → receive a plain-language simplification.
- Upload two documents → request a comparison → see materiality-ranked differences rendered.
- Upload a document → ask a question → receive an answer with a visible, clickable citation.
- Request an export → download a file that opens correctly in a PDF/DOCX viewer.

### 11.4 LLM Quality Evaluation Suite

- A fixed, version-controlled golden dataset (Section 1.4: 50 documents, human-annotated clause spans/types and expected Q&A answers) is run against every change to a prompt template in `apps/api/app/prompts/`.
- Automated scoring: clause extraction precision/recall, citation-validity rate for Q&A, and readability delta for simplification, computed identically to the Section 1.4 methodology.
- A prompt change is not merged if it regresses any Section 1.4 metric below its stated target.

### 11.5 Coverage Targets

- Backend service layer (`services/`): ≥ 80% line coverage, enforced in CI.
- Security-critical paths (auth, file validation, ownership checks, PII disclosure flow): 100% coverage, enforced in CI as a separate, non-waivable gate.

---

## 12. Security Considerations

- **Authentication:** JWT access tokens (15-minute expiry) plus refresh tokens (14-day expiry, rotated on use); passwords hashed with argon2id; no plaintext password ever logged or persisted.
- **Authorization:** every resource-scoped endpoint checks `owner_id` against the authenticated user before returning or mutating data; there is no cross-user access path in the MVP's single-tenant model.
- **Input validation:** all request bodies validated against Pydantic schemas; uploaded files validated by magic-byte inspection (not extension), size-capped at 20 MB, and scanned with ClamAV (or an equivalent malware scanner) before being persisted to S3.
- **Data protection:** TLS 1.2+ enforced on all external traffic; S3 server-side encryption at rest for raw documents and export artifacts; PostgreSQL encryption at rest via the managed database provider's native support.
- **Third-party LLM data handling:** users are shown an explicit, un-skippable disclosure before their first upload stating that document content is sent to Anthropic (generation) and Voyage AI (embeddings) under those providers' respective data-handling terms; the disclosure and the user's acknowledgment are recorded in `audit_logs`.
- **Rate limiting:** per-user and per-IP request throttling on upload and every LLM-calling endpoint, enforced via Redis-backed counters, to control both abuse and third-party API cost exposure.
- **Audit logging:** every document upload, export, deletion, and LLM call is written to the append-only `audit_logs` table with actor, action, resource, and IP address; the database role used by the application has no `UPDATE`/`DELETE` grant on this table.
- **Legal disclaimers:** every simplification, clause-extraction, comparison, and chat response includes a persistent "this is general information, not legal advice" disclaimer in both the API response payload and the rendered UI; the disclaimer is not a dismissible one-time modal.
- **Right to deletion:** `DELETE /documents/{document_id}` performs a hard delete of the document row, its chunks, embeddings, clauses, associated chat sessions/messages, and the underlying S3 object, to support user-initiated data removal requests.
- **Dependency and application security:** automated dependency vulnerability scanning (e.g., Dependabot) on every pull request; output that echoes user-uploaded document text into the UI is rendered as plain text/escaped HTML, never as raw HTML, to prevent stored XSS via a maliciously crafted document; all database access goes through the ORM's parameterized queries, with no raw string-interpolated SQL.
- **Secrets:** API keys and JWT signing secrets are never logged, are loaded exclusively from the environment/secrets manager, and are rotated on a defined schedule; least-privilege IAM roles are used for the application's S3 and secrets-manager access.

---

## 13. Performance & Scalability Notes

### 13.1 Bottlenecks

| Bottleneck | Cause | Mitigation |
|---|---|---|
| LLM generation latency | Long documents require multiple chunk-level calls for full simplification | Map-reduce summarization with parallelized per-chunk calls; streaming responses to reduce perceived latency |
| OCR processing | Tesseract OCR on scanned pages is CPU-bound and slow relative to native text extraction | Run OCR only on pages confirmed to lack a text layer; run OCR as a separate Celery queue with its own worker pool so it cannot starve faster ingestion jobs |
| Embedding generation | Network round-trip per batch to the Voyage AI API | Batch chunks into the largest request size the Voyage AI API supports per call rather than one request per chunk |
| Synchronous upload blocking | Naively processing a document inline with the upload request would block the request thread for the full ingestion pipeline | Upload endpoint only validates and stores the raw file synchronously; all parsing/embedding work is deferred to the async job queue (Section 2.3, step 1–3) |
| Database connection exhaustion under load | Each API worker holding open connections during long-running requests | Connection pooling (PgBouncer or SQLAlchemy pool tuning) sized to expected concurrent worker count |

### 13.2 Scalability Targets

- Documents up to 100 pages (approximately 50,000 tokens) are supported via hierarchical chunking and map-reduce summarization rather than a single-pass prompt.
- p95 API latency ≤ 2 s for all non-LLM-backed endpoints (metadata fetch, status polling, history retrieval).
- p95 latency for LLM-backed endpoints as stated in Section 1.4 (15 s for simplification of a ≤ 20-page document, 5 s per chat turn).
- Stateless API and worker processes scale horizontally behind a load balancer / autoscaling group, keyed on CPU utilization for API workers and queue depth for Celery workers.

### 13.3 Cost Optimization

- Tiered model usage: `claude-haiku-4-5-20251001` for high-volume, low-complexity classification calls; `claude-sonnet-5` reserved for generation tasks where output quality materially affects user trust (simplification, Q&A synthesis, comparison summaries).
- Per-request token budget caps to prevent a single pathological document from generating unbounded LLM spend.
- Semantic response caching keyed on `(document_hash, normalized_query)` for chat, so a repeated or near-duplicate question against the same document does not trigger a redundant LLM call within a configurable time window.

---

## 14. Open Questions / Assumptions

**Assumptions made in this specification:**

- The MVP targets English-language documents only; multi-language support is deferred to a future phase.
- Users are individuals evaluating their own documents, not law firms requiring multi-tenant team workspaces; no cross-user document sharing exists in this version.
- No integration with a live attorney marketplace or booking system exists in this version; the "lawyer-prep brief" export is a standalone document, not a referral mechanism.
- Anthropic's and Voyage AI's respective API terms permit sending user-uploaded document content for processing as described in Section 12; this must be confirmed against each provider's current terms of service and, if required, a data processing agreement, before handling real users' documents in production.
- Default document and derived-data retention period is 30 days from last access unless the user takes an explicit action to keep the document, pending a final product/legal decision (see below).

**Open questions requiring a decision before or during Phase 6:**

- Which jurisdiction(s) should clause-type definitions and risk heuristics be tuned for at launch — the system defaults to jurisdiction-agnostic clause categories (Section 6.2) that are common across common-law contract structures, but risk severity can differ materially by jurisdiction (e.g., enforceability of non-compete clauses varies significantly by region).
- What is the final data retention policy for uploaded documents, derived chunks/embeddings, and chat history — the 30-day default in this document is an assumption, not a confirmed product decision.
- Should the malware-scanning step (Section 12) block upload synchronously (adding latency to the upload response) or run asynchronously with the document held in a quarantined state until cleared — this affects the exact status-transition timing in Section 6.2's `documents.status` enum.
- Should a pre-send PII redaction step be added before document content is sent to third-party LLM/embedding providers, and if so, what redaction accuracy is acceptable given the risk of redacting content that is itself legally relevant (e.g., a named party in a contract)?
