# LegalLens Web App

Next.js 14 frontend for LegalLens document analysis platform.

## Design System

**Status:** ✅ Complete (v1, 2026-09-22)

Full design specification in `.context/ui-design-system.md`. Key decisions:

- **Color:** Primary blue-700 for trust/authority
- **Typography:** Inter font, 6-level scale (display → caption)
- **Risk indicators:** Color + icon + label (WCAG-compliant)
- **Spacing:** 7-step scale (4px → 48px)

## Stack

- **Framework:** Next.js 14+ (App Router)
- **Styling:** Tailwind CSS
- **State:** TanStack Query
- **TypeScript:** Strict mode

## Directory Structure

```
src/
├── app/                    # App Router pages
│   ├── upload/            # Upload view
│   ├── document/[id]/     # Document detail
│   ├── compare/           # Comparison view
│   ├── chat/              # Chat view (standalone)
│   └── auth/              # Authentication pages
├── components/            # Reusable UI components
│   ├── RiskBadge.tsx     # Risk level indicator
│   ├── ClauseCard.tsx    # Extracted clause display
│   ├── DiffView.tsx      # Comparison diff view
│   ├── ChatPane.tsx      # Q&A interface
│   ├── Header.tsx        # Global navigation
│   └── DisclaimerFooter.tsx  # Compliance disclaimer
├── hooks/                 # Custom React hooks
├── lib/                   # Utilities & API client
├── styles/               # Global CSS
└── types/                # TypeScript types
```

## Core Components

### RiskBadge

Displays clause risk level with WCAG-compliant encoding:
- Low: Green + checkmark ✓
- Medium: Amber + warning ⚠
- High: Red + octagon ⛔

```tsx
<RiskBadge level="high" />
```

### ClauseCard

Displays extracted clause with excerpt, risk, and rationale:

```tsx
<ClauseCard
  clauseType="auto_renewal"
  textExcerpt="Contract renews automatically..."
  riskLevel="high"
  riskRationale="May result in unintended extension"
  pageNumber={3}
  onClick={() => handleClauseClick()}
/>
```

### DiffView

Shows clause-aligned comparison with materiality:

```tsx
<DiffView
  clauseType="termination"
  materiality="significant"
  excerpts={[
    { documentId: '1', documentName: 'v1.pdf', text: '...' },
    { documentId: '2', documentName: 'v2.pdf', text: '...' }
  ]}
  diffSummary="Notice periods differ significantly"
  materialityRationale="Creates execution risk"
/>
```

### ChatPane

Q&A interface with citation support:

```tsx
<ChatPane
  documentId="doc-123"
  documentName="contract.pdf"
  messages={chatMessages}
  onSendMessage={(content) => sendToAPI(content)}
  onCitationClick={(citation) => scrollToSource(citation)}
  onClose={() => setChatOpen(false)}
/>
```

## Views

### 1. Upload (`/upload`)

- Drag-and-drop upload zone
- File validation (PDF, DOCX, TXT, max 20MB)
- Recent documents list
- Status indicators (uploaded, processing, ready, failed)

### 2. Document Detail (`/document/[id]`)

Three-tab interface:
- **Simplified:** Plain-language summary with citations
- **Original:** Extracted document text
- **Clauses:** Risk-assessed clause cards (grid layout)

Optional chat pane (400px slide-over).

### 3. Compare (`/compare`)

- Document chip selection (2-5 documents)
- Clause type + materiality filters
- DiffView cards with highlighted changes
- Materiality ranking

### 4. Chat (embedded in Document Detail)

- Message history (user + assistant bubbles)
- Streaming response support
- Clickable citation links
- Persistent disclaimer footer

## API Integration

Default API URL: `http://localhost:8000`

Override via environment variable:

```bash
NEXT_PUBLIC_API_URL=https://api.legallens.example.com
```

### Key Endpoints

```typescript
// Upload document
POST /api/v1/documents
Content-Type: multipart/form-data

// Get document status
GET /api/v1/documents/{id}/status

// Simplify document
POST /api/v1/documents/{id}/simplify

// Extract clauses
POST /api/v1/documents/{id}/extract-clauses

// Create comparison
POST /api/v1/comparisons
Body: { document_ids: ["id1", "id2"] }

// Chat message
POST /api/v1/documents/{id}/chat/sessions/{session_id}/messages
Body: { content: "What are the payment terms?" }
```

## Development

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Type check
npm run type-check

# Lint
npm run lint

# Build for production
npm run build

# Start production server
npm start
```

## Environment Variables

Required:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000  # Backend API URL
```

Optional:

```env
NODE_ENV=development|production
```

## Design Tokens (Tailwind)

Custom tokens in `tailwind.config.ts`:

```typescript
colors: {
  primary: '#1d4ed8',      // Main actions
  'risk-low-bg': '#f0fdf4',
  'risk-medium-bg': '#fffbeb',
  'risk-high-bg': '#fef2f2',
  // ... see config for full palette
}
```

Typography:

```typescript
fontSize: {
  'display': '2.25rem',    // Page titles
  'title': '1.5rem',       // Section headers
  'body': '1rem',          // Primary content
  'caption': '0.75rem',    // Auxiliary text
}
```

## Testing

```bash
# Run tests
npm test

# Watch mode
npm test -- --watch
```

Test files: `src/components/__tests__/`

## Accessibility

WCAG AA compliant:

- ✅ Risk/materiality indicators use icon + color + label
- ✅ All interactive elements have visible focus rings
- ✅ Semantic HTML (header, nav, main, aside)
- ✅ Minimum 4.5:1 contrast for body text
- ✅ All images have alt text or aria-labels

## Compliance

### Persistent Disclaimer

Every view with LLM-generated content displays:

> "This tool provides informational summaries, not legal advice. Consult a licensed attorney for legal guidance."

Implemented via `<DisclaimerFooter />` component (sticky, never dismissible).

### Citation Requirements

- Every Q&A answer must cite source passages
- Citations are clickable and navigate to source
- Displayed as superscript numbers with expanded details

### Content Security

- No raw HTML rendering of user-uploaded content
- All document text escaped (React default behavior)
- XSS prevention via strict CSP (production)

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Performance Targets

- First Contentful Paint: < 1.5s
- Time to Interactive: < 3.5s
- Lighthouse score: > 90

## Known Limitations

1. **Mobile responsiveness:** Optimized for desktop (1024px+). Mobile layout functional but not fully optimized.

2. **Offline support:** No offline functionality. Requires active internet connection.

3. **Large documents:** UI may slow with documents > 100 pages. Consider pagination for clause view.

4. **Real-time collaboration:** Not supported in v1.

## Troubleshooting

### API Connection Failed

Check API is running:

```bash
curl http://localhost:8000/health
```

Verify `NEXT_PUBLIC_API_URL` matches backend URL.

### Styles Not Loading

Clear Next.js cache:

```bash
rm -rf .next
npm run dev
```

### Type Errors

Regenerate types from backend schemas:

```bash
# (Assuming type generation script exists)
npm run generate-types
```

## Contributing

1. Follow design system tokens (no arbitrary values)
2. Add tests for new components
3. Update `.context/ui-design-system.md` for visual changes
4. Ensure WCAG AA compliance

## License

Internal use only. All rights reserved.
