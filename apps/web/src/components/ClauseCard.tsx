import React from 'react';
import { RiskBadge } from './RiskBadge';

interface ClauseCardProps {
  clauseType: string;
  textExcerpt: string;
  riskLevel: 'low' | 'medium' | 'high';
  riskRationale: string;
  pageNumber?: number;
  onClick?: () => void;
}

export function ClauseCard({
  clauseType,
  textExcerpt,
  riskLevel,
  riskRationale,
  pageNumber,
  onClick,
}: ClauseCardProps) {
  return (
    <article
      className={`
        bg-white rounded-md border border-gray-200 shadow-sm
        p-4 hover:shadow-md transition-shadow
        ${onClick ? 'cursor-pointer' : ''}
      `}
      onClick={onClick}
    >
      <header className="flex items-start justify-between gap-3 mb-3">
        <h3 className="text-heading capitalize">
          {clauseType.replace(/_/g, ' ')}
        </h3>
        <RiskBadge level={riskLevel} />
      </header>

      <blockquote className="mb-3 p-3 bg-gray-50 rounded border-l-4 border-primary">
        <p className="text-body-sm text-gray-700 italic line-clamp-3">
          &ldquo;{textExcerpt}&rdquo;
        </p>
      </blockquote>

      <div className="text-body-sm text-gray-600">
        <p className="mb-2">
          <span className="font-medium text-gray-900">Why this matters:</span>{' '}
          {riskRationale}
        </p>
        {pageNumber && (
          <p className="text-caption text-gray-500">
            Found on page {pageNumber}
          </p>
        )}
      </div>
    </article>
  );
}
