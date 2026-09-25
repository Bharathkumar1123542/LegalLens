'use client';

import React, { useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Header } from '@/components/Header';
import { DisclaimerFooter } from '@/components/DisclaimerFooter';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { ErrorAlert } from '@/components/ErrorAlert';
import { DiffView } from '@/components/DiffView';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

type MaterialityFilter = 'all' | 'critical' | 'significant' | 'minor' | 'none';
type ClauseTypeFilter = 'all' | string;

interface Document {
  id: string;
  originalFilename: string;
}

interface ComparisonResult {
  clauseType: string;
  materiality: 'none' | 'minor' | 'significant' | 'critical';
  excerpts: Array<{
    documentId: string;
    documentName: string;
    text: string;
    changes?: Array<{ type: 'added' | 'removed' | 'modified'; text: string }>;
  }>;
  diffSummary: string;
  materialityRationale?: string;
}

function ComparePageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const [selectedDocs, setSelectedDocs] = useState<Document[]>([]);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [materialityFilter, setMaterialityFilter] = useState<MaterialityFilter>('all');
  const [clauseTypeFilter, setClauseTypeFilter] = useState<ClauseTypeFilter>('all');

  // Mock data - replace with actual API calls
  const mockResults: ComparisonResult[] = [
    {
      clauseType: 'termination',
      materiality: 'significant',
      excerpts: [
        {
          documentId: '1',
          documentName: 'contract-v2.pdf',
          text: 'Either party may terminate with 30 days notice.',
          changes: [
            { type: 'modified', text: '30 days' },
          ],
        },
        {
          documentId: '2',
          documentName: 'vendor-agreement.pdf',
          text: 'Either party may terminate with 60 days notice.',
          changes: [
            { type: 'modified', text: '60 days' },
          ],
        },
        {
          documentId: '3',
          documentName: 'final-draft.docx',
          text: 'Vendor may terminate immediately; Client requires 90 days notice.',
          changes: [
            { type: 'added', text: 'immediately' },
            { type: 'modified', text: '90 days' },
          ],
        },
      ],
      diffSummary: 'Notice period varies from 30 to 90 days. Vendor has asymmetric immediate termination right in final-draft.',
      materialityRationale: 'Mismatched termination clauses create risk if parties assume consistent terms across versions.',
    },
    {
      clauseType: 'payment_terms',
      materiality: 'minor',
      excerpts: [
        {
          documentId: '1',
          documentName: 'contract-v2.pdf',
          text: 'Payment due net 30 days. Late payments incur 1.5% monthly interest.',
        },
        {
          documentId: '2',
          documentName: 'vendor-agreement.pdf',
          text: 'Payment due net 30 days. Late payments incur 1.5% monthly interest.',
        },
        {
          documentId: '3',
          documentName: 'final-draft.docx',
          text: 'Payment due net 30 days. Late payments incur 2.0% monthly interest.',
          changes: [
            { type: 'modified', text: '2.0%' },
          ],
        },
      ],
      diffSummary: 'Payment terms are consistent (net 30) across all documents. Late payment interest differs slightly in final-draft (2.0% vs 1.5%).',
      materialityRationale: 'Interest rate difference is minor and within typical commercial ranges.',
    },
    {
      clauseType: 'indemnification',
      materiality: 'critical',
      excerpts: [
        {
          documentId: '1',
          documentName: 'contract-v2.pdf',
          text: 'Client indemnifies Vendor against third-party claims arising from Client\'s use of the services.',
        },
        {
          documentId: '2',
          documentName: 'vendor-agreement.pdf',
          text: 'Mutual indemnification for third-party claims arising from each party\'s breach.',
          changes: [
            { type: 'added', text: 'Mutual' },
          ],
        },
        {
          documentId: '3',
          documentName: 'final-draft.docx',
          text: 'Client indemnifies Vendor for all claims, including Vendor\'s own negligence.',
          changes: [
            { type: 'added', text: 'including Vendor\'s own negligence' },
          ],
        },
      ],
      diffSummary: 'Indemnification scope varies significantly. Final-draft includes unusual broad indemnity covering vendor negligence.',
      materialityRationale: 'Indemnifying a party for their own negligence is highly unusual and creates substantial financial risk for the indemnifying party.',
    },
  ];

  const documents: Document[] = [
    { id: '1', originalFilename: 'contract-v2.pdf' },
    { id: '2', originalFilename: 'vendor-agreement.pdf' },
    { id: '3', originalFilename: 'final-draft.docx' },
  ];

  const filteredResults = mockResults.filter(result => {
    if (materialityFilter !== 'all' && result.materiality !== materialityFilter) {
      return false;
    }
    if (clauseTypeFilter !== 'all' && result.clauseType !== clauseTypeFilter) {
      return false;
    }
    return true;
  });

  const handleExport = () => {
    // TODO: Implement export
    alert('Export comparison report coming soon');
  };

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Header
        title="Compare Documents"
        showBack
        backHref="/upload"
        actions={
          <button
            onClick={handleExport}
            className="px-4 py-2 text-body-sm font-medium text-white bg-primary rounded-md hover:bg-primary-hover transition-colors"
          >
            Export Report
          </button>
        }
      />

      <main className="flex-1 px-6 py-8">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* Document Chips */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-body-sm text-gray-600 mr-2">Comparing:</span>
              {documents.map((doc, idx) => (
                <React.Fragment key={doc.id}>
                  <span className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-100 text-gray-900 text-body-sm rounded-full">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                    </svg>
                    {doc.originalFilename}
                  </span>
                  {idx < documents.length - 1 && (
                    <span className="text-gray-400">•</span>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2">
              <span className="text-body-sm text-gray-700 font-medium">Clause type:</span>
              <select
                value={clauseTypeFilter}
                onChange={(e) => setClauseTypeFilter(e.target.value)}
                className="px-3 py-2 text-body-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="all">All clauses</option>
                <option value="indemnification">Indemnification</option>
                <option value="termination">Termination</option>
                <option value="payment_terms">Payment terms</option>
                <option value="auto_renewal">Auto-renewal</option>
                <option value="limitation_of_liability">Limitation of liability</option>
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-body-sm text-gray-700 font-medium">Materiality:</span>
              <select
                value={materialityFilter}
                onChange={(e) => setMaterialityFilter(e.target.value as MaterialityFilter)}
                className="px-3 py-2 text-body-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="all">All levels</option>
                <option value="critical">Critical only</option>
                <option value="significant">Significant+</option>
                <option value="minor">Minor+</option>
                <option value="none">No difference</option>
              </select>
            </label>
          </div>

          {/* Results */}
          {error && (
            <ErrorAlert message={error} onRetry={() => setError(null)} />
          )}

          {comparing ? (
            <div className="bg-white rounded-lg border border-gray-200 p-12">
              <LoadingSpinner message="Analyzing documents..." />
            </div>
          ) : (
            <div className="space-y-6">
              {filteredResults.length === 0 ? (
                <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
                  <svg className="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-body text-gray-600">
                    No differences found with the selected filters.
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <p className="text-body-sm text-gray-600">
                      Showing {filteredResults.length} {filteredResults.length === 1 ? 'difference' : 'differences'}
                    </p>
                  </div>

                  {filteredResults.map((result, idx) => (
                    <DiffView
                      key={`${result.clauseType}-${idx}`}
                      clauseType={result.clauseType}
                      materiality={result.materiality}
                      excerpts={result.excerpts}
                      diffSummary={result.diffSummary}
                      materialityRationale={result.materialityRationale}
                    />
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </main>

      <DisclaimerFooter />
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" message="Loading comparison..." />
      </div>
    }>
      <ComparePageContent />
    </Suspense>
  );
}
