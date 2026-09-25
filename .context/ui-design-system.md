# UI Design System — LegalLens

> 🆕 NEW DECISION (2026-09-22): Complete design system for LegalLens
> Replaces placeholder tokens from ui-context.md with production-ready design.
> Source: UI specification task (Figma-ready design deliverable)

## Overview

LegalLens is a document-trust product handling sensitive legal material. The visual language conveys **authority, clarity, and reliability** while remaining accessible (WCAG AA compliant).

## Design Tokens

### Color Palette

| Token | Value | Usage |
|---|---|---|
| **Primary (Trust)** | | |
| primary | `#1d4ed8` (blue-700) | Primary actions, links, accents |
| primary-hover | `#1e40af` (blue-800) | Hover states |
| primary-50 | `#eff6ff` | Light backgrounds |
| **Neutrals** | | |
| gray-50 | `#f9fafb` | Page background |
| gray-100 | `#f3f4f6` | Card backgrounds |
| gray-200 | `#e5e7eb` | Borders |
| gray-400 | `#9ca3af` | Placeholder text |
| gray-600 | `#4b5563` | Secondary text |
| gray-900 | `#111827` | Primary text |
| white | `#ffffff` | Surface |

### Risk Levels (WCAG-compliant with icons)

Risk levels use **color + icon + label** to avoid color-only dependence:

| Level | Color | Background | Icon | Pattern |
|---|---|---|---|---|
| Low | `#16a34a` (green-600) | `#f0fdf4` (green-50) | ✓ | Checkmark |
| Medium | `#d97706` (amber-600) | `#fffbeb` (amber-50) | ⚠ | Triangle |
| High | `#dc2626` (red-600) | `#fef2f2` (red-50) | ⛔ | Octagon |

### Materiality Levels (Pattern + Border + Weight)

Materiality uses **icon pattern + border color + text weight**:

| Level | Color | Background | Icon | Weight |
|---|---|---|---|---|
| None | `#6b7280` (gray-500) | `#f3f4f6` (gray-100) | = | Semibold |
| Minor | `#2563eb` (blue-600) | `#eff6ff` (blue-50) | • | Semibold |
| Significant | `#d97706` (amber-600) | `#fef3c7` (amber-100) | •• | Bold |
| Critical | `#dc2626` (red-600) | `#fee2e2` (red-100) | ••• | Bold + red text |

### Typography Scale (Inter font)

| Token | Size | Line Height | Weight | Usage |
|---|---|---|---|---|
| display | 36px / 2.25rem | 2.5rem | 700 | Page titles |
| title | 24px / 1.5rem | 2rem | 600 | Section headers |
| heading | 18px / 1.125rem | 1.75rem | 600 | Card titles |
| body | 16px / 1rem | 1.5rem | 400 | Primary content |
| body-sm | 14px / 0.875rem | 1.25rem | 400 | Metadata, labels |
| caption | 12px / 0.75rem | 1rem | 500 | Timestamps, auxiliary |

**Letter spacing:**
- Display: -0.02em (optical correction)
- Title: -0.01em (optical correction)
- Caption: +0.01em (improves readability at small size)

### Spacing Scale

| Token | Value | Usage |
|---|---|---|
| xs | 4px / 0.25rem | Tight inline spacing |
| sm | 8px / 0.5rem | Icon-to-text gap |
| md | 16px / 1rem | Card padding, stack spacing |
| lg | 24px / 1.5rem | Section spacing |
| xl | 32px / 2rem | View padding |
| 2xl | 48px / 3rem | Major section breaks |

### Border Radius

| Token | Value | Usage |
|---|---|---|
| sm | 4px | Badges |
| md | 8px | Cards, inputs |
| lg | 12px | Modals, overlays |

### Shadows

| Token | Value | Usage |
|---|---|---|
| sm | `0 1px 2px rgba(0,0,0,0.05)` | Subtle elevation |
| md | `0 4px 6px rgba(0,0,0,0.07)` | Cards |
| lg | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |

## Component Specifications

### RiskBadge

**Purpose:** Display clause risk level with WCAG-compliant visual encoding.

**Variants:**
- Low: Green bg + checkmark icon
- Medium: Amber bg + triangle icon
- High: Red bg + octagon icon

**Dimensions:**
- Height: auto (py-1)
- Padding: px-2.5
- Font: text-xs (12px)
- Border: 1px solid (matches color)
- Border radius: sm (4px)

### ClauseCard

**Purpose:** Display extracted clause with excerpt, risk level, and rationale.

**Layout:**
- Container: bg-white, border-gray-200, rounded-md, p-4, shadow-sm
- Header: flex justify-between
  - Title: text-heading, capitalize (converts snake_case)
  - RiskBadge: top-right
- Excerpt: blockquote, bg-gray-50, border-l-4 border-primary, p-3, italic
- Rationale: text-body-sm, gray-600
- Page number: text-caption, gray-500

**States:**
- Default: shadow-sm
- Hover: shadow-md (if clickable)

### DiffView

**Purpose:** Show clause-aligned comparison with materiality indication.

**Layout:**
- Container: bg-white, rounded-md, shadow-md, p-6, border-l-4 (materiality color)
- Header: flex justify-between
  - Clause type: text-xl, capitalize
  - Materiality badge: icon + label
- Excerpts: stacked per document, bg-gray-50, border-l-2
- Diff highlighting:
  - Added: bg-green-100 + underline
  - Removed: bg-red-100 + line-through
  - Modified: bg-amber-100
- Summary: border-t, pt-4

**Materiality encoding:**
- Border-left-4 color
- Icon pattern (=, •, ••, •••)
- Text weight (semibold/bold)
- Critical adds red text color

### ChatPane

**Purpose:** Q&A interface with citation support.

**Layout:**
- Width: 400px fixed (desktop), full-width slide-over (mobile)
- Header: h-12, bg-white, border-b
- Messages: flex-1, overflow-y-auto, px-4, py-4
- Input: h-12, border-t, px-4, py-4
- Disclaimer footer: h-auto, bg-gray-50, border-t

**Message bubbles:**
- User: bg-primary, text-white, ml-auto (right-aligned)
- Assistant: bg-gray-100, text-gray-900, mr-auto (left-aligned)
- Max-width: 85% of pane
- Padding: px-4, py-3
- Border radius: lg

**Citations:**
- Border-top separator
- Clickable buttons (text-caption, text-primary)
- Superscript numbers

### Header

**Purpose:** Global navigation and page titles.

**Layout:**
- Height: 64px (h-16)
- Padding: px-6
- Background: white, border-b
- Logo: left (LegalLens with shield icon)
- Actions: right (buttons, dropdowns)

### DisclaimerFooter

**Purpose:** Persistent compliance disclaimer (never dismissible).

**Layout:**
- Height: 48px (h-12)
- Sticky bottom
- Background: amber-50
- Border: amber-200
- Text: body-sm, amber-900, center-aligned
- Icon: warning triangle inline

## View Layouts

### Upload View

**Route:** `/upload`

**Layout:**
- Max-width: 800px, centered
- Upload zone: 560px × 320px
  - Dashed border (gray-300)
  - Drag-over state: bg-primary-50, border-primary-400
- Recent docs: list, max 5 items
- Footer: DisclaimerFooter

### Document Detail View

**Route:** `/document/[id]`

**Layout:**
- Three-column: sidebar (240px) + main (flex-1) + chat (400px, conditional)
- Sidebar: Contents navigation
- Main: Tabbed content (Simplified, Original, Clauses)
- Header actions: Chat, Compare, Export buttons

### Compare View

**Route:** `/compare`

**Layout:**
- Max-width: 1024px (5xl), centered
- Document chips: horizontal scroll if >3 docs
- Filters: dropdown selects
- DiffView cards: stacked with lg spacing

### Chat View

**Route:** `/document/[id]/chat` (embedded pane)

**Layout:**
- Slide-over pane (400px width)
- Full-height with sticky header/footer
- Scrollable message area

## States

### Loading States

**Component:** LoadingSpinner
- Sizes: sm (16px), md (32px), lg (48px)
- Animation: rotate spin
- Optional message below spinner

### Error States

**Component:** ErrorAlert
- Red bg-red-50, border-red-200
- Icon: X in circle (red-400)
- Optional retry button

### Empty States

**Pattern:**
- Centered layout
- Icon (gray-400, 48px)
- Message (body, gray-600)
- Optional CTA button

## Implementation Notes

### Accessibility (WCAG AA)

- ✅ Risk/materiality use icon + color + label (not color-only)
- ✅ All interactive elements have focus rings (ring-2, ring-primary)
- ✅ Minimum contrast ratios: 4.5:1 for body text, 3:1 for large text
- ✅ All images/icons have aria-labels
- ✅ Semantic HTML (header, nav, main, aside, footer)

### Responsive Breakpoints

- Mobile: < 768px (single column, full-width panes)
- Tablet: 768px - 1023px (two columns where applicable)
- Desktop: ≥ 1024px (three columns, fixed sidebar widths)

### Dark Mode

**Status:** Not implemented in v1.
**Rationale:** Document-reading applications typically require light backgrounds for readability. Dark mode deferred until user research validates demand.

## Gaps & Future Decisions

**Items NOT covered by current spec:**

1. **Animation timing:** No specific easing curves or duration values defined. Using Tailwind defaults (transition-colors, etc.)

2. **Keyboard shortcuts:** No defined shortcuts for common actions (Cmd+K for search, etc.)

3. **Illustration system:** Text-only empty states used. Consider adding illustration assets when brand resources available.

4. **Mobile-specific gestures:** Swipe-to-delete, pull-to-refresh not specified.

5. **Offline states:** No design for offline/connection-lost scenarios.

## Maintenance

**When to update this file:**
- New component patterns added
- Design tokens changed
- Accessibility requirements updated
- User feedback drives visual changes

**Who approves changes:**
- Design lead (visual changes)
- Compliance officer (disclaimer, risk indicator changes)
- Engineering lead (feasibility)
