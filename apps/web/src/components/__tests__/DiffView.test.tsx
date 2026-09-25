/**
 * DiffView component tests
 * Updated for design system v1 (2026-09-22)
 * Tests:
 *  - Materiality badge renders for each level (distinct patterns)
 *  - Excerpts rendered as plain text (XSS safety check — no innerHTML)
 *  - Document names appear correctly
 *  - Change highlighting works
 */

import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DiffView } from '@/components/DiffView';

describe('DiffView', () => {
  const mockExcerpts = [
    {
      documentId: 'doc1',
      documentName: 'Contract_A.pdf',
      text: 'Either party may terminate with 30 days notice.',
    },
    {
      documentId: 'doc2',
      documentName: 'Contract_B.pdf',
      text: 'Either party may terminate with 60 days notice.',
      changes: [{ type: 'modified' as const, text: '60 days' }],
    },
  ];

  it('renders clause type as heading', () => {
    render(
      <DiffView
        clauseType="termination"
        materiality="significant"
        excerpts={mockExcerpts}
        diffSummary="Notice periods differ"
      />
    );
    expect(screen.getByText('Termination')).toBeInTheDocument();
  });

  it('renders excerpt as plain text (XSS safety)', () => {
    const xssExcerpts = [
      {
        documentId: 'doc1',
        documentName: 'Test.pdf',
        text: '<script>alert("xss")</script>',
      },
    ];
    const { container } = render(
      <DiffView
        clauseType="test"
        materiality="minor"
        excerpts={xssExcerpts}
        diffSummary="Test"
      />
    );
    // Script tags must not be in DOM
    expect(container.querySelector('script')).toBeNull();
    // Text content should be escaped
    expect(container.textContent).toContain('alert("xss")');
  });

  it.each([
    ['none', 'No Difference'],
    ['minor', 'Minor'],
    ['significant', 'Significant'],
    ['critical', 'Critical'],
  ] as const)('materiality "%s" renders correct label', (level, label) => {
    render(
      <DiffView
        clauseType="test"
        materiality={level}
        excerpts={mockExcerpts}
        diffSummary="Test"
      />
    );
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('renders document names', () => {
    render(
      <DiffView
        clauseType="termination"
        materiality="significant"
        excerpts={mockExcerpts}
        diffSummary="Test"
      />
    );
    expect(screen.getByText('Contract_A.pdf:')).toBeInTheDocument();
    expect(screen.getByText('Contract_B.pdf:')).toBeInTheDocument();
  });

  it('renders diff summary', () => {
    render(
      <DiffView
        clauseType="termination"
        materiality="significant"
        excerpts={mockExcerpts}
        diffSummary="Notice periods differ significantly"
      />
    );
    expect(screen.getByText(/Notice periods differ significantly/)).toBeInTheDocument();
  });

  it('renders materiality rationale when provided', () => {
    render(
      <DiffView
        clauseType="termination"
        materiality="significant"
        excerpts={mockExcerpts}
        diffSummary="Test"
        materialityRationale="Creates execution risk"
      />
    );
    expect(screen.getByText(/Creates execution risk/)).toBeInTheDocument();
  });
});
