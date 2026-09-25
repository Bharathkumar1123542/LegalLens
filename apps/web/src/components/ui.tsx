/**
 * Shared UI components — LegalLens Web
 * Small, reusable primitives used across pages.
 */

'use client';

import { type ReactNode } from 'react';

// ── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ size = 'md', label = 'Loading…' }: { size?: 'sm' | 'md' | 'lg'; label?: string }) {
  const sizes = { sm: 'w-4 h-4 border-2', md: 'w-8 h-8 border-2', lg: 'w-12 h-12 border-4' };
  return (
    <div className="flex items-center justify-center" role="status" aria-label={label}>
      <div className={`${sizes[size]} border-slate-200 border-t-indigo-600 rounded-full animate-spin`} />
      <span className="sr-only">{label}</span>
    </div>
  );
}

// ── Alert / Error banner ──────────────────────────────────────────────────────
export function ErrorBanner({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      <span aria-hidden className="flex-shrink-0 mt-0.5">⚠</span>
      <span className="flex-1">{message}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="flex-shrink-0 text-red-400 hover:text-red-600" aria-label="Dismiss">
          ✕
        </button>
      )}
    </div>
  );
}

// ── Status pill for document processing ──────────────────────────────────────
export function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    uploaded: 'bg-slate-100 text-slate-600',
    processing: 'bg-blue-100 text-blue-700',
    ready: 'bg-emerald-100 text-emerald-700',
    failed: 'bg-red-100 text-red-700',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] ?? 'bg-slate-100 text-slate-600'}`}>
      {status === 'processing' && (
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
      )}
      {status}
    </span>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
export function EmptyState({ icon, title, description, action }: {
  icon: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
      <span className="text-5xl">{icon}</span>
      <h3 className="text-base font-semibold text-slate-700">{title}</h3>
      {description && <p className="text-sm text-slate-400 max-w-sm">{description}</p>}
      {action}
    </div>
  );
}

// ── Section heading ───────────────────────────────────────────────────────────
export function SectionHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h2 className="text-xl font-bold text-slate-900">{title}</h2>
      {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
    </div>
  );
}

// ── Card wrapper ─────────────────────────────────────────────────────────────
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm p-6 ${className}`}>
      {children}
    </div>
  );
}

// ── Legal Disclaimer (standalone, for inline use) ─────────────────────────────
// ui-context.md: persistent, not dismissible
export function LegalDisclaimer() {
  return (
    <div className="disclaimer text-center" role="note" aria-label="Legal disclaimer">
      This is general information about your document, not legal advice. Always consult a
      qualified attorney before acting on this information.
    </div>
  );
}

// ── Progress bar for ingestion ────────────────────────────────────────────────
const STAGE_PROGRESS: Record<string, number> = {
  extracting_text: 25,
  ocr: 45,
  chunking: 65,
  embedding: 85,
};

export function IngestionProgress({ stage }: { stage: string | null }) {
  const pct = stage ? (STAGE_PROGRESS[stage] ?? 10) : 0;
  return (
    <div className="space-y-1">
      <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-500 rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-slate-400 text-center">{pct}% complete</p>
    </div>
  );
}
