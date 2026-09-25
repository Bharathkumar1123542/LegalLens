import React from 'react';

type RiskLevel = 'low' | 'medium' | 'high';

interface RiskBadgeProps {
  level: RiskLevel;
  className?: string;
}

const RISK_CONFIG = {
  low: {
    icon: '✓',
    label: 'Low Risk',
    colorClasses: 'bg-risk-low-bg text-risk-low-DEFAULT border-risk-low-border',
  },
  medium: {
    icon: '⚠',
    label: 'Medium Risk',
    colorClasses: 'bg-risk-medium-bg text-risk-medium-DEFAULT border-risk-medium-border',
  },
  high: {
    icon: '⛔',
    label: 'High Risk',
    colorClasses: 'bg-risk-high-bg text-risk-high-DEFAULT border-risk-high-border',
  },
} as const;

export function RiskBadge({ level, className = '' }: RiskBadgeProps) {
  const config = RISK_CONFIG[level];

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2.5 py-1
        text-xs font-medium rounded-sm
        border ${config.colorClasses}
        ${className}
      `}
      role="status"
      aria-label={`Risk level: ${config.label}`}
    >
      <span className="text-sm leading-none" aria-hidden="true">
        {config.icon}
      </span>
      <span>{config.label}</span>
    </span>
  );
}
