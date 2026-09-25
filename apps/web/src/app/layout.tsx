/**
 * Root layout — LegalLens
 * architecture.md §5: src/app/layout.tsx
 * ui-context.md: persistent disclaimer visible on every page (non-negotiable).
 * TanStack Query provider wraps the entire app.
 */

import type { Metadata } from 'next';
import Link from 'next/link';
import '@/styles/globals.css';
import { Providers } from './providers';
import { UserMenu } from '@/components/UserMenu';

export const metadata: Metadata = {
  title: 'LegalLens — Understand Your Legal Documents',
  description:
    'Plain-language summaries, clause extraction, document comparison, and grounded Q&A for contracts, leases, and terms of service. Not legal advice.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="font-sans">
      <body className="min-h-screen flex flex-col bg-gray-50 antialiased">
        <Providers>
          {/* Global navigation - Design system v1 (2026-09-22) */}
          <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/95 backdrop-blur-sm">
            <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
              <Link href="/" className="flex items-center gap-2">
                <svg className="w-8 h-8 text-primary" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5zm0 18c-4 0-7-3.58-7-8V8.3l7-3.11L19 8.3V12c0 4.42-3 8-7 8z"/>
                  <path d="M9 12l2 2 4-4"/>
                </svg>
                <span className="text-title font-bold text-gray-900">LegalLens</span>
              </Link>
              <nav className="flex items-center gap-1" aria-label="Primary navigation">
                <Link
                  href="/upload"
                  className="px-3 py-2 rounded-md text-body-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
                >
                  Upload
                </Link>
                <Link
                  href="/compare"
                  className="px-3 py-2 rounded-md text-body-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
                >
                  Compare
                </Link>
                <div className="ml-2">
                  <UserMenu />
                </div>
              </nav>
            </div>
          </header>

          <main className="flex-1 w-full">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
