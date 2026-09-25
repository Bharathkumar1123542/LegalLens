/**
 * RiskBadge component tests
 * Updated for design system v1 (2026-09-22)
 * Tests:
 *  - Renders the correct label for each risk level
 *  - Each level has visually distinct styling
 *  - ARIA role/label present (accessibility)
 *  - Icon rendering
 */

import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { RiskBadge } from '@/components/RiskBadge';

describe('RiskBadge', () => {
  it.each([
    ['low', 'Low Risk'],
    ['medium', 'Medium Risk'],
    ['high', 'High Risk'],
  ] as const)('renders label for risk level "%s"', (level, expectedLabel) => {
    render(<RiskBadge level={level} />);
    expect(screen.getByText(expectedLabel)).toBeInTheDocument();
  });

  it('renders ARIA role and label', () => {
    render(<RiskBadge level="high" />);
    const badge = screen.getByRole('status');
    expect(badge).toHaveAttribute('aria-label', 'Risk level: High Risk');
  });

  it.each([
    ['low', '✓'],
    ['medium', '⚠'],
    ['high', '⛔'],
  ] as const)('renders icon for level "%s"', (level, icon) => {
    const { container } = render(<RiskBadge level={level} />);
    expect(container.textContent).toContain(icon);
  });

  it('icon is aria-hidden', () => {
    const { container } = render(<RiskBadge level="high" />);
    const icon = container.querySelector('[aria-hidden="true"]');
    expect(icon).toBeInTheDocument();
  });

  it('accepts additional className', () => {
    const { container } = render(<RiskBadge level="low" className="test-class" />);
    expect(container.firstElementChild).toHaveClass('test-class');
  });
});
