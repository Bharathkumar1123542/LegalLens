import React from 'react';

type MaterialityLevel = 'none' | 'minor' | 'significant' | 'critical';

interface DocumentExcerpt {
  documentId: string;
  documentName: string;
  text: string;
  changes?: Array<{ type: 'added' | 'removed' | 'modified'; text: string }>;
}

interface DiffViewProps {
  clauseType: string;
  materiality: MaterialityLevel;
  excerpts: DocumentExcerpt[];
  diffSummary: string;
  materialityRationale?: string;
}

const MATERIALITY_CONFIG = {
  none: {
    label: 'No Difference',
    icon: '=',
    borderColor: 'border-l-materiality-none-border',
    bgColor: 'bg-materiality-none-bg',
    textColor: 'text-materiality-none-DEFAULT',
    headerWeight: 'font-semibold',
  },
  minor: {
    label: 'Minor',
    icon: '•',
    borderColor: 'border-l-materiality-minor-border',
    bgColor: 'bg-materiality-minor-bg',
    textColor: 'text-materiality-minor-DEFAULT',
    headerWeight: 'font-semibold',
  },
  significant: {
    label: 'Significant',
    icon: '••',
    borderColor: 'border-l-materiality-significant-border',
    bgColor: 'bg-materiality-significant-bg',
    textColor: 'text-materiality-significant-DEFAULT',
    headerWeight: 'font-bold',
  },
  critical: {
    label: 'Critical',
    icon: '•••',
    borderColor: 'border-l-materiality-critical-border',
    bgColor: 'bg-materiality-critical-bg',
    textColor: 'text-materiality-critical-DEFAULT',
    headerWeight: 'font-bold',
  },
} as const;

export function DiffView({
  clauseType,
  materiality,
  excerpts,
  diffSummary,
  materialityRationale,
}: DiffViewProps) {
  const config = MATERIALITY_CONFIG[materiality];

  return (
    <section
      className={`
        bg-white rounded-md shadow-md p-6
        border-l-4 ${config.borderColor}
      `}
      aria-labelledby={`diff-${clauseType}`}
    >
      <header className="flex items-start justify-between gap-4 mb-4">
        <h2
          id={`diff-${clauseType}`}
          className={`text-xl ${config.headerWeight} text-gray-900 capitalize`}
        >
          {clauseType.replace(/_/g, ' ')}
        </h2>
        <span
          className={`
            inline-flex items-center gap-2 px-3 py-1.5
            text-body-sm font-medium rounded-sm
            ${config.bgColor} ${config.textColor}
          `}
          role="status"
          aria-label={`Materiality: ${config.label}`}
        >
          <span aria-hidden="true" className="text-base leading-none">
            {config.icon}
          </span>
          <span>{config.label}</span>
        </span>
      </header>

      <div className="space-y-4 mb-4">
        {excerpts.map((excerpt) => (
          <div key={excerpt.documentId} className="space-y-2">
            <p className="text-body-sm font-medium text-gray-900">
              {excerpt.documentName}:
            </p>
            <div className="p-4 bg-gray-50 rounded-sm border-l-2 border-gray-300">
              <p className="text-body-sm text-gray-800 whitespace-pre-wrap">
                {excerpt.changes ? (
                  <DiffText changes={excerpt.changes} />
                ) : (
                  excerpt.text
                )}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="pt-4 border-t border-gray-200">
        <p className="text-body-sm text-gray-900 mb-2">
          <span className="font-semibold">Summary:</span> {diffSummary}
        </p>
        {materialityRationale && materiality !== 'none' && (
          <p className="text-body-sm text-gray-700">
            <span className="font-semibold">Why {config.label.toLowerCase()}:</span>{' '}
            {materialityRationale}
          </p>
        )}
      </div>
    </section>
  );
}

function DiffText({ changes }: { changes: Array<{ type: 'added' | 'removed' | 'modified'; text: string }> }) {
  return (
    <>
      {changes.map((change, idx) => {
        if (change.type === 'added') {
          return (
            <mark
              key={idx}
              className="bg-green-100 underline decoration-green-600"
            >
              {change.text}
            </mark>
          );
        }
        if (change.type === 'removed') {
          return (
            <del
              key={idx}
              className="bg-red-100 line-through decoration-red-600"
            >
              {change.text}
            </del>
          );
        }
        if (change.type === 'modified') {
          return (
            <mark key={idx} className="bg-amber-100">
              {change.text}
            </mark>
          );
        }
        return <span key={idx}>{change.text}</span>;
      })}
    </>
  );
}
