# Component Library — LegalLens

Design system v1 (2026-09-22). See `.context/ui-design-system.md` for complete specification.

## Core Components

### RiskBadge

**Purpose:** Display clause risk level with WCAG-compliant visual encoding.

**Props:**

```typescript
interface RiskBadgeProps {
  level: 'low' | 'medium' | 'high';
  className?: string;
}
```

**Variants:**

| Level | Color | Icon | Label |
|---|---|---|---|
| low | green-600 | ✓ | Low Risk |
| medium | amber-600 | ⚠ | Medium Risk |
| high | red-600 | ⛔ | High Risk |

**Usage:**

```tsx
import { RiskBadge } from '@/components';

<RiskBadge level="high" />
<RiskBadge level="medium" className="ml-2" />
```

**Accessibility:**
- `role="status"` for screen readers
- `aria-label` describes full risk level
- Icon marked `aria-hidden="true"`

---

### ClauseCard

**Purpose:** Display extracted clause with excerpt, risk level, and rationale.

**Props:**

```typescript
interface ClauseCardProps {
  clauseType: string;         // snake_case, e.g. "auto_renewal"
  textExcerpt: string;        // Quoted clause text
  riskLevel: 'low' | 'medium' | 'high';
  riskRationale: string;      // 1-2 sentence explanation
  pageNumber?: number;        // Optional source page
  onClick?: () => void;       // Optional click handler
}
```

**States:**

- **Default:** white background, subtle shadow
- **Hover:** elevated shadow (if onClick provided)
- **Focus:** ring-2 ring-primary

**Usage:**

```tsx
import { ClauseCard } from '@/components';

<ClauseCard
  clauseType="indemnification"
  textExcerpt="Client shall indemnify Vendor against..."
  riskLevel="high"
  riskRationale="Broad indemnity including vendor negligence is unusual"
  pageNumber={7}
  onClick={() => navigateToClause('clause-123')}
/>
```

**Layout:**
- Max 2 columns on desktop (grid-cols-2)
- Single column on mobile
- Excerpt line-clamped to 3 lines

---

### DiffView

**Purpose:** Show clause-aligned comparison with materiality indication.

**Props:**

```typescript
type MaterialityLevel = 'none' | 'minor' | 'significant' | 'critical';

interface DocumentExcerpt {
  documentId: string;
  documentName: string;
  text: string;
  changes?: Array<{
    type: 'added' | 'removed' | 'modified';
    text: string;
  }>;
}

interface DiffViewProps {
  clauseType: string;
  materiality: MaterialityLevel;
  excerpts: DocumentExcerpt[];
  diffSummary: string;
  materialityRationale?: string;
}
```

**Materiality Encoding:**

| Level | Border | Icon | Weight | Text Color |
|---|---|---|---|---|
| none | gray | = | semibold | gray-700 |
| minor | blue | • | semibold | blue-700 |
| significant | amber | •• | bold | amber-700 |
| critical | red | ••• | bold | red-700 |

**Change Highlighting:**

- **Added:** green-100 bg + underline
- **Removed:** red-100 bg + line-through
- **Modified:** amber-100 bg

**Usage:**

```tsx
import { DiffView } from '@/components';

<DiffView
  clauseType="termination"
  materiality="significant"
  excerpts={[
    {
      documentId: 'doc1',
      documentName: 'contract-v1.pdf',
      text: 'Terminate with 30 days notice',
      changes: [{ type: 'modified', text: '30 days' }]
    },
    {
      documentId: 'doc2',
      documentName: 'contract-v2.pdf',
      text: 'Terminate with 60 days notice',
      changes: [{ type: 'modified', text: '60 days' }]
    }
  ]}
  diffSummary="Notice period doubled in v2"
  materialityRationale="Significant change to termination rights"
/>
```

**Accessibility:**
- Section labeled with `aria-labelledby`
- Materiality status has `role="status"`
- Icon marked `aria-hidden="true"`

---

### ChatPane

**Purpose:** Q&A interface with citation support.

**Props:**

```typescript
interface Citation {
  chunkId: string;
  pageNumber: number;
  excerpt: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

interface ChatPaneProps {
  documentId: string;
  documentName: string;
  messages: Message[];
  isStreaming?: boolean;
  onSendMessage: (content: string) => void;
  onCitationClick?: (citation: Citation) => void;
  onClose?: () => void;
}
```

**States:**

- **Empty:** Placeholder prompt
- **Streaming:** Three-dot animation in assistant bubble
- **Error:** Red text in assistant bubble with retry option

**Layout:**
- Fixed width: 400px (desktop)
- Full width slide-over (mobile)
- Sticky header + footer
- Scrollable message area

**Usage:**

```tsx
import { ChatPane } from '@/components';
import { useState } from 'react';

function DocumentPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  
  return (
    <ChatPane
      documentId="doc-123"
      documentName="contract.pdf"
      messages={messages}
      isStreaming={false}
      onSendMessage={(content) => {
        // Send to API, update messages
      }}
      onCitationClick={(citation) => {
        // Navigate to source
      }}
      onClose={() => setChatOpen(false)}
    />
  );
}
```

**Message Format:**

- User: Right-aligned, primary background, white text
- Assistant: Left-aligned, gray-100 background, gray-900 text
- Max-width: 85% of pane

**Citations:**
- Displayed below assistant messages
- Clickable buttons with superscript numbers
- Format: `¹ Page 5`

---

### Header

**Purpose:** Global navigation and page context.

**Props:**

```typescript
interface HeaderProps {
  title?: string;           // Page title (optional)
  showBack?: boolean;       // Show back button
  backHref?: string;        // Back button destination
  actions?: React.ReactNode; // Right-side actions (buttons, etc.)
}
```

**Usage:**

```tsx
import { Header } from '@/components';

// Simple header
<Header />

// With title and back button
<Header
  title="contract-v2.pdf"
  showBack
  backHref="/upload"
/>

// With actions
<Header
  title="Compare Documents"
  showBack
  actions={
    <>
      <button>Filter</button>
      <button>Export</button>
    </>
  }
/>
```

**Layout:**
- Height: 64px (h-16)
- Logo: Left (home link)
- Title: Center-left
- Actions: Right

---

### DisclaimerFooter

**Purpose:** Persistent compliance disclaimer.

**Props:** None (stateless component)

**Usage:**

```tsx
import { DisclaimerFooter } from '@/components';

<DisclaimerFooter />
```

**Behavior:**
- Always visible (sticky bottom)
- Never dismissible (compliance requirement)
- Amber background for visibility
- Warning icon inline

**Text:**
> "This tool provides informational summaries, not legal advice. Consult a licensed attorney for legal guidance."

---

### LoadingSpinner

**Purpose:** Loading state indicator.

**Props:**

```typescript
interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  message?: string;
}
```

**Sizes:**
- sm: 16px (w-4 h-4)
- md: 32px (w-8 h-8) — default
- lg: 48px (w-12 h-12)

**Usage:**

```tsx
import { LoadingSpinner } from '@/components';

<LoadingSpinner />
<LoadingSpinner size="lg" message="Processing document..." />
```

---

### ErrorAlert

**Purpose:** Error state display with retry option.

**Props:**

```typescript
interface ErrorAlertProps {
  title?: string;           // Default: "Error"
  message: string;          // Error description
  onRetry?: () => void;     // Optional retry handler
}
```

**Usage:**

```tsx
import { ErrorAlert } from '@/components';

<ErrorAlert
  title="Upload Failed"
  message="File size exceeds 20MB limit"
/>

<ErrorAlert
  message="Connection error"
  onRetry={() => refetch()}
/>
```

**Layout:**
- Red background (red-50)
- Error icon left
- Message body center
- Retry button below (if provided)

---

## Compound Patterns

### Document Detail Layout

```tsx
<div className="flex">
  {/* Sidebar */}
  <aside className="w-60 bg-gray-50 border-r">
    <nav>...</nav>
  </aside>

  {/* Main content */}
  <main className="flex-1 p-8">
    <ClauseCard ... />
  </main>

  {/* Chat pane (conditional) */}
  {chatOpen && (
    <div className="w-96">
      <ChatPane ... />
    </div>
  )}
</div>
```

### Empty State Pattern

```tsx
<div className="text-center py-12">
  <svg className="w-12 h-12 text-gray-400 mx-auto mb-4">
    {/* Icon */}
  </svg>
  <p className="text-body text-gray-600">
    No documents found
  </p>
  <button className="mt-4 ...">
    Upload your first document
  </button>
</div>
```

---

## Design Tokens Reference

Quick reference for common tokens:

**Colors:**
```css
bg-primary          /* #1d4ed8 */
text-gray-900       /* #111827 */
border-gray-200     /* #e5e7eb */
```

**Typography:**
```css
text-display        /* 36px, bold */
text-title          /* 24px, semibold */
text-body           /* 16px */
text-caption        /* 12px */
```

**Spacing:**
```css
p-md                /* 16px */
gap-lg              /* 24px */
mx-xl               /* 32px horizontal */
```

**Responsive:**
```css
sm:grid-cols-2      /* 2 columns at 640px+ */
md:w-96             /* 384px width at 768px+ */
lg:max-w-5xl        /* 1024px max at 1024px+ */
```

---

## Testing Components

Each component should have:

1. **Snapshot test:** Visual regression
2. **Interaction test:** Click handlers, form submission
3. **Accessibility test:** ARIA attributes, keyboard navigation

Example:

```typescript
import { render, screen } from '@testing-library/react';
import { RiskBadge } from './RiskBadge';

describe('RiskBadge', () => {
  it('renders high risk with correct icon and label', () => {
    render(<RiskBadge level="high" />);
    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-label',
      'Risk level: High Risk'
    );
  });
});
```

---

## Future Components

Candidates for addition:

- **DocumentSelector:** Multi-select for comparison
- **ExportDialog:** Export format + options picker
- **FilterPanel:** Clause type + risk level filters
- **ProgressBar:** Upload/processing progress
- **Toast:** Success/error notifications
- **Tooltip:** Hover definitions for legal terms
