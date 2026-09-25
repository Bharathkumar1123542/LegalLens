# Code Standards — LegalLens

> Governs: implementation rules and conventions.
> Source: bootstrapped from `docs/implementation.md` v1.0.

## Naming Conventions

| Context | Convention | Example |
|---|---|---|
| REST API paths | kebab-case, plural nouns, versioned | `/api/v1/documents/{document_id}/extract-clauses` |
| Database tables/columns | snake_case, plural table names | `document_chunks`, `risk_level` |
| Python identifiers | snake_case functions/variables, PascalCase classes | `generate_embeddings()`, `class ComparisonResult` |
| TypeScript identifiers | camelCase variables/functions, PascalCase components/types | `useDocumentStatus()`, `type ChatMessage` |
| Environment variables | UPPER_SNAKE_CASE | `ANTHROPIC_API_KEY` |
| Enum values (stored) | snake_case | `limitation_of_liability` |

## Language / Framework Conventions

- **Backend:** Python 3.11+, FastAPI, fully async (`async def`) on every
  I/O-bound path (DB, LLM calls, embedding calls, S3) so the event loop is
  never blocked. Request/response validation via Pydantic schemas in
  `schemas/`, mirroring `models/` 1:1 where applicable.
- **Frontend:** TypeScript throughout; types in `src/types/` mirror backend
  Pydantic schemas so a backend shape change is a visible frontend type
  error, not a silent runtime mismatch.
- **Config:** a single `Settings` class (Pydantic `BaseSettings`) is the
  only way env vars are read — a missing required variable must fail
  application startup immediately, never fail lazily on first use.
- **Database access:** ORM (SQLAlchemy) with parameterized queries only.
  **No raw string-interpolated SQL, anywhere.**
- **Prompts:** versioned template files under `apps/api/app/prompts/`
  (`simplify.md`, `extract_clauses.md`, `compare.md`, `chat.md`) — prompt
  text is not to be inlined ad hoc in service code.

## Error Handling & Edge Cases (must be handled, not deferred)

| Failure mode | Detection | Required behavior |
|---|---|---|
| Unsupported file type | Magic-byte check at upload | `400`, clear message, file not stored |
| Corrupted/unparseable file | Parser exception during ingestion | `Document.status=failed`, `failure_reason` set |
| Scanned/image-only PDF page | No extractable text layer | OCR fallback; below-threshold confidence → flagged `low_confidence` with a visible caveat, not silently dropped |
| Oversized document (>~400 chunks) | Chunk count ceiling exceeded | Switch to hierarchical map-reduce summarization; inform client of longer response time |
| LLM API timeout/rate limit/5xx | Exception/timeout from Claude or Voyage SDK | Exponential backoff, up to 3 attempts; final failure → `502` distinguishing "temporary service issue" vs. data problem; request logged for reprocessing, never silently dropped |
| LLM hallucination / ungrounded claim | Post-generation citation validator finds an unmatched claim/citation | Reject and regenerate once with stricter grounding; second failure → return "insufficient information in this document to answer that," never an unverified answer |
| Ambiguous/conflicting clauses in comparison | Model explicitly asked to flag ambiguity, not resolve it | Tag `materiality=critical` + note recommending professional review; system never asserts which version is "better" |
| Non-English document | Language detection returns non-`en` with high confidence | Accept upload, warn client output quality is unvalidated for that language, store `language` field |
| Duplicate upload | `file_hash_sha256` matches an existing doc for the same owner | Return the existing `Document`, do not reprocess |
| Expired/invalid access token | JWT verification fails | `401`; client uses refresh token transparently, or redirects to login if that has also expired |
| Partial failure in multi-doc comparison | A document has `status != ready`, or fails mid-job | `400` at job creation if not ready; mid-job failure → `ComparisonJob.status=failed` with the specific failing `document_id` recorded — never a partial result that looks complete |

## Security Rules (apply to every PR touching these paths)

- **Input validation:** every request body validated against a Pydantic
  schema; uploaded files validated by **magic-byte inspection, not
  extension**, size-capped at 20 MB, scanned with ClamAV (or equivalent)
  before persisting to S3.
- **Authorization:** every resource-scoped endpoint checks `owner_id`
  against the authenticated user before returning or mutating data. No
  cross-user access path exists in the single-tenant MVP model — an
  ownership check is not optional on any new endpoint.
- **XSS:** output that echoes user-uploaded document text into the UI is
  rendered as plain text / escaped HTML, never raw HTML.
- **Secrets:** never logged; loaded only from environment/secrets manager;
  rotated on a defined schedule.
- **Passwords:** argon2id hashing only; plaintext password never logged or
  persisted anywhere.
- **Audit logging:** every document upload, export, deletion, and LLM call
  writes an `audit_logs` row. The application's DB role must have **no
  UPDATE/DELETE grant** on `audit_logs`.
- **Legal disclaimer:** every simplification/extraction/comparison/chat
  response includes the "not legal advice" disclaimer in both the API
  payload and the rendered UI — enforce this in the response schema, not
  only in frontend copy, so it can't be dropped by a UI change.

## Cost Controls (apply when touching LLM-calling code)

- Tiered model usage: `claude-haiku-4-5-20251001` for high-volume,
  low-complexity classification calls (e.g. per-chunk clause pre-filter);
  `claude-sonnet-5` reserved for generation where output quality
  materially affects user trust (simplification, Q&A synthesis, comparison
  summaries). Don't default new LLM calls to the larger model without a
  reason.
- Per-request token budget caps to prevent one pathological document from
  generating unbounded spend.
- Semantic response caching keyed on `(document_hash, normalized_query)`
  for chat, so a repeated/near-duplicate question doesn't trigger a
  redundant LLM call within a configurable window.

## Testing Strategy

- **Unit (pytest, Jest):** parsers against known-good/known-corrupt
  fixtures; chunking boundaries/overlap/token counts; every Pydantic
  schema rejects invalid payloads; clause regex pre-filter against labeled
  fixtures per clause type; frontend component tests for `DiffView`,
  `RiskBadge`, citation-rendering against fixed props.
- **Integration:** full ingestion pipeline (upload→parse→chunk→embed)
  asserting `status=ready` and correctly ordered non-empty
  `document_chunks`; API contract tests for every endpoint (success +
  documented error responses); LLM prompt/response contract tests using
  recorded cassette-style fixtures — **no live API calls in CI**;
  ownership/authorization tests — a second user's token must get
  `403`/`404` on every resource-scoped endpoint.
- **E2E (Playwright):** upload→simplification; two-doc upload→compare→see
  materiality-ranked diffs; upload→ask a question→see a clickable
  citation; request export→download opens correctly.
- **LLM quality eval suite:** the 50-document golden dataset (see
  `project-overview.md` Success Criteria) runs against every change to a
  prompt template in `apps/api/app/prompts/`. **A prompt change is not
  merged if it regresses any success-criteria metric below its target.**
- **Coverage gates (CI-enforced):** backend `services/` ≥ 80% line
  coverage. Security-critical paths (auth, file validation, ownership
  checks, PII disclosure flow): **100% coverage, non-waivable.**
