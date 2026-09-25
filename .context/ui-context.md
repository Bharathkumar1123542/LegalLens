# UI Context — LegalLens

> Governs: theme, colors, typography, component conventions.
> Source: bootstrapped from `docs/implementation.md` v1.0.

## ⚠️ Design system — placeholder decision recorded (2026-09-17)

The source specification defines no visual design system. Per workflow rule "no
assumption-driven scope," this gap was surfaced explicitly. The following
**explicit placeholder decision** has been recorded and implemented:

> **Decision**: Use Tailwind CSS default palette with the following
> **named placeholder tokens** for compliance-required visual distinctions.
> These are NOT brand tokens. Replace when real brand guidelines exist.

| Purpose | Token class | Colour (placeholder) |
|---|---|---|
| Risk: low | `.risk-low` | emerald-500 / emerald-50 |
| Risk: medium | `.risk-medium` | amber-500 / amber-50 |
| Risk: high | `.risk-high` | red-500 / red-50 |
| Materiality: none | `.materiality-none` | gray-500 / gray-100 |
| Materiality: minor | `.materiality-minor` | blue-500 / blue-100 |
| Materiality: significant | `.materiality-significant` | amber-500 / amber-100 |
| Materiality: critical | `.materiality-critical` | red-500 / red-100 |

**Typography**: Inter (system fallback `ui-sans-serif`) — placeholder.

This decision is recorded here so it cannot silently become the permanent
design system through repetition. When real brand tokens are supplied,
update this file and `tailwind.config.ts`.

## What the source spec *does* establish

### Stack

- **Framework:** Next.js 14+, App Router, React 18+, TypeScript.
- **Styling:** Tailwind CSS (utility-first — chosen specifically because
  the comparison/diff UI needs many small conditional styles for risk
  levels and diff highlighting).
- **Server state:** TanStack Query (the UI is dominated by server-owned
  async state: job status polling, chat history, comparison results).

### Primary views (`src/app/`)

- Upload
- Document detail (`document/[id]`)
- Compare
- Chat

### Known components (`src/components/`)

- `DiffView` — renders the clause-aligned comparison diff with materiality
  highlighting.
- `RiskBadge` — renders a clause's risk level (`low`/`medium`/`high`).
- `ClauseCard` — renders an extracted clause with its excerpt and risk
  rationale.
- `ChatPane` — renders the document Q&A chat interface.

### Known hooks (`src/hooks/`)

`useDocumentStatus`, `useChatSession`, `useComparison` — thin wrappers
around TanStack Query for the corresponding polling/session state.

### Non-negotiable UI behaviors (these are product/compliance requirements,
not design choices, and apply regardless of what visual system is chosen)

- **Persistent disclaimer.** Every simplification, clause-extraction,
  comparison, and chat response must render a "this is general
  information, not legal advice" disclaimer in the UI. It must be
  **persistent, not a dismissible one-time modal.**
- **Visible, clickable citations.** Every Q&A answer and every
  simplification must render its citations so the user can see which
  passage of the source document backs a given claim (per
  `architecture.md` §3, step 6–7).
- **No raw HTML from document content.** Any UI surface that echoes
  user-uploaded document text must render it as escaped plain text, never
  as raw HTML, to prevent stored XSS via a maliciously crafted document
  (see `code-standards.md`).
- **Risk levels and materiality ratings must be visually distinguishable**
  at a glance (`RiskBadge`, `DiffView`) — exact colors are part of the
  unresolved design-system gap above, but the three risk levels
  (`low`/`medium`/`high`) and four materiality levels
  (`none`/`minor`/`significant`/`critical`) must each be distinct, not
  just labeled in text.
