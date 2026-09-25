# Project Overview — LegalLens

> Governs: product definition, goals, features, scope. Read first.
> Source: bootstrapped from `docs/implementation.md` v1.0.

## Problem Statement

Non-lawyers routinely sign contracts, leases, terms of service, and policies they
do not fully understand, because the documents are long, written in dense legal
register, and expensive to have reviewed by a professional. LegalLens is a
GenAI-powered web application that helps a non-lawyer understand, compare, and
act on legal documents they already have — without generating legal advice or
replacing a licensed attorney.

## Purpose

LegalLens ingests one or more legal documents (contracts, agreements, policies,
leases, offer letters, terms of service) and provides:

- Plain-language simplification of the full document or selected clauses.
- Extraction and risk-flagging of the clauses that matter (obligations,
  liabilities, termination conditions, auto-renewals, etc.).
- Side-by-side comparison of two or more documents, ranked by how materially
  they differ.
- Document-grounded question answering, with every answer traceable to a
  specific passage in the source document.
- Exportable artifacts a user can act on: a plain-language summary, an action
  checklist, and a "questions for your lawyer" brief.

## Scope

### In scope (MVP)

| Capability | Boundary |
|---|---|
| Document upload | PDF, DOCX, TXT; ≤ 20 MB per file; ≤ 5 documents per comparison job |
| Language | English-language source documents only |
| Simplification | Full-document and per-clause plain-language rewrite, selectable reading level |
| Clause & risk extraction | 10 predefined clause categories, 3-level risk rating |
| Comparison | Clause-aligned diff across 2–5 documents with a materiality rating per difference |
| Q&A | Document-grounded chat with mandatory source citation per answer |
| Export | Summary, action checklist, and lawyer-prep brief, each as PDF, DOCX, or Markdown |
| Accounts | Single-tenant, individual user accounts (no team/workspace sharing) |

### Explicitly out of scope for this version

- Generating legal advice, legal opinions, or predictions of case outcomes.
- E-signature, contract execution, or redlining/negotiation workflows.
- Multi-language document support.
- Team workspaces, matter management, or multi-user collaboration on one document.
- Referral or booking integration with a live attorney or law firm.
- Jurisdiction-certified accuracy guarantees (the system is jurisdiction-aware
  where possible but does not warrant compliance with any specific
  jurisdiction's law).

**Do not implement anything in the out-of-scope list without an explicit,
deliberate update to this file first (see `ai-workflow-rules.md`, "No
context drift").**

## Success Criteria

Measured against a fixed evaluation set (50 human-annotated legal documents
spanning contracts, leases, and ToS documents, held out from prompt-tuning work):

| Metric | Target | Measurement method |
|---|---|---|
| Readability improvement | Simplified output scores ≥ 4 grade levels lower on Flesch-Kincaid Grade Level than the source text | Automated scoring on a 20-document benchmark subset |
| Clause extraction precision | ≥ 0.85 | Compared against human-annotated clause spans/types on the 50-doc gold set |
| Clause extraction recall | ≥ 0.80 | Same gold set |
| Q&A groundedness | ≥ 95% of answers cite a verifiable source chunk; 0% fabricated citations | Automated citation-validity check + manual spot audit of 10% of eval answers |
| Simplification latency | p95 ≤ 15 s for documents ≤ 20 pages, measured after ingestion completes | Load test against staging environment |
| Chat response latency | p95 ≤ 5 s per turn | Load test against staging environment |
| Ingestion success rate | ≥ 99% for supported file types under 20 MB | Production telemetry, rolling 30-day window |
| Usability | ≥ 80% unassisted task completion across simplify/compare/ask-a-question | Moderated usability test, minimum 5 participants |

## Open product questions (carried from spec Section 14)

These require a decision before or during Phase 6 and are not yet resolved —
do not assume an answer:

- Which jurisdiction(s) should clause-type definitions and risk heuristics be
  tuned for at launch?
- What is the final data retention policy for uploaded documents, derived
  chunks/embeddings, and chat history? (30-day default is an assumption, not
  a confirmed product decision.)
- Should malware scanning block upload synchronously or run asynchronously
  with the document held in a quarantined state?
- Should a pre-send PII redaction step be added before content is sent to
  third-party LLM/embedding providers?
