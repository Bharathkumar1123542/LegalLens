/**
 * Home page — LegalLens
 * Landing page with primary action cards and API health indicator.
 */

'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

type ApiStatus = 'checking' | 'ok' | 'error';

const FEATURES = [
  {
    icon: '📄',
    title: 'Plain-language simplification',
    desc: 'Get a plain-English rewrite of any contract at your chosen reading level.',
    href: '/upload',
    cta: 'Upload a document',
    primary: true,
  },
  {
    icon: '⚠️',
    title: 'Clause & risk extraction',
    desc: 'Identify the 10 most important clause types — indemnification, auto-renewal, termination, and more — each with a risk rating.',
    href: '/upload',
    cta: 'Try it',
    primary: false,
  },
  {
    icon: '🔍',
    title: 'Side-by-side comparison',
    desc: 'Compare 2–5 documents clause by clause. Material differences are ranked by severity.',
    href: '/compare',
    cta: 'Compare documents',
    primary: false,
  },
  {
    icon: '💬',
    title: 'Grounded Q&A',
    desc: 'Ask any question about your document. Every answer cites the exact passage it came from.',
    href: '/upload',
    cta: 'Upload & ask',
    primary: false,
  },
];

export default function HomePage() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking');

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => setApiStatus(r.ok ? 'ok' : 'error'))
      .catch(() => setApiStatus('error'));
  }, []);

  return (
    <div className="space-y-16">
      {/* Hero */}
      <section className="text-center space-y-6 pt-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-semibold mb-2">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
          AI-powered · Not legal advice
        </div>

        <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
          Understand your legal<br />
          <span className="text-indigo-600">documents in minutes</span>
        </h1>

        <p className="text-lg text-slate-500 max-w-xl mx-auto leading-relaxed">
          LegalLens simplifies contracts, leases, and terms of service into plain English —
          with clause extraction, document comparison, and grounded Q&amp;A.
        </p>

        <div className="flex justify-center gap-4 flex-wrap">
          <Link
            href="/upload"
            className="px-7 py-3 rounded-xl bg-indigo-600 text-white font-semibold text-sm
                       hover:bg-indigo-700 transition-colors shadow-md shadow-indigo-200"
          >
            Upload a document →
          </Link>
          <Link
            href="/compare"
            className="px-7 py-3 rounded-xl border border-slate-300 text-slate-700 font-semibold text-sm
                       hover:bg-slate-50 transition-colors"
          >
            Compare documents
          </Link>
        </div>

        {/* API status dot */}
        <div className="flex justify-center">
          <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${
            apiStatus === 'ok'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : apiStatus === 'error'
              ? 'bg-red-50 border-red-200 text-red-600'
              : 'bg-slate-50 border-slate-200 text-slate-500'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${
              apiStatus === 'ok' ? 'bg-emerald-500' : apiStatus === 'error' ? 'bg-red-500' : 'bg-slate-400 animate-pulse'
            }`} />
            {apiStatus === 'ok' ? 'API connected' : apiStatus === 'error' ? 'API offline — start the backend' : 'Connecting…'}
          </span>
        </div>
      </section>

      {/* Feature cards */}
      <section>
        <div className="grid sm:grid-cols-2 gap-5">
          {FEATURES.map((f) => (
            <div key={f.title}
              className="rounded-2xl border border-slate-200 bg-white p-6 space-y-3 hover:border-indigo-200 hover:shadow-sm transition-all"
            >
              <div className="text-3xl">{f.icon}</div>
              <h2 className="text-base font-bold text-slate-800">{f.title}</h2>
              <p className="text-sm text-slate-500 leading-relaxed">{f.desc}</p>
              <Link
                href={f.href}
                className={`inline-flex items-center gap-1 text-sm font-medium transition-colors ${
                  f.primary
                    ? 'text-indigo-600 hover:text-indigo-800'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {f.cta} →
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 text-center" role="note">
        <strong>Not legal advice.</strong> LegalLens provides general information about your documents.
        Always consult a qualified attorney before signing or acting on any legal document.
      </div>
    </div>
  );
}
