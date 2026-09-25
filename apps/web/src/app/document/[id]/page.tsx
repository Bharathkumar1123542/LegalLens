'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Header } from '@/components/Header';
import { DisclaimerFooter } from '@/components/DisclaimerFooter';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { ErrorAlert } from '@/components/ErrorAlert';
import { ClauseCard } from '@/components/ClauseCard';
import { ChatPane } from '@/components/ChatPane';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { ExportMenu } from '@/components/ExportMenu';
import { useDocumentStatus } from '@/hooks/useDocumentStatus';
import { useChatSession } from '@/hooks/useChatSession';
import { getClauses, simplifyDocument, createChatSession } from '@/lib/api-client';
import type { Clause, SimplificationResponse, Citation } from '@/types';

type TabType = 'simplified' | 'original' | 'clauses';

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const documentId = params.id as string;
  
  const [activeTab, setActiveTab] = useState<TabType>('simplified');
  const [chatOpen, setChatOpen] = useState(false);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [highlightedChunkId, setHighlightedChunkId] = useState<string | null>(null);
  const originalContentRef = React.useRef<HTMLDivElement>(null);
  
  // Poll document status
  const { document, isProcessing, isReady, isFailed, processingStage, failureReason } = 
    useDocumentStatus({ documentId });

  // Fetch clauses when document is ready
  const { data: clauses = [], isLoading: clausesLoading } = useQuery<Clause[]>({
    queryKey: ['clauses', documentId],
    queryFn: () => getClauses(documentId),
    enabled: isReady,
  });

  // Simplification mutation
  const simplifyMutation = useMutation({
    mutationFn: () => simplifyDocument(documentId),
    onSuccess: (data) => {
      queryClient.setQueryData(['simplification', documentId], data);
    },
  });

  // Get or create simplification
  const { data: simplification } = useQuery<SimplificationResponse>({
    queryKey: ['simplification', documentId],
    queryFn: () => simplifyDocument(documentId),
    enabled: isReady && activeTab === 'simplified',
  });

  // Create chat session
  const createChatMutation = useMutation({
    mutationFn: () => createChatSession(documentId),
    onSuccess: (session) => {
      setChatSessionId(session.id);
      setChatOpen(true);
    },
  });

  // Chat session hook (only when session exists)
  const chatSession = useChatSession(documentId, chatSessionId || undefined);

  const handleCitationClick = (citation: Citation) => {
    setActiveTab('original');
    
    // Highlight and scroll to the chunk
    setHighlightedChunkId(citation.chunk_id);
    
    // Wait for tab content to render, then scroll
    setTimeout(() => {
      const chunkElement = window.document.getElementById(`chunk-${citation.chunk_id}`);
      if (chunkElement) {
        chunkElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
    
    // Clear highlight after 3 seconds
    setTimeout(() => {
      setHighlightedChunkId(null);
    }, 3100);
  };

  const handleExportClick = () => {
    setExportMenuOpen(!exportMenuOpen);
  };

  const handleCompareClick = () => {
    router.push(`/compare?docs=${documentId}`);
  };

  const handleChatClick = () => {
    if (chatSessionId) {
      setChatOpen(!chatOpen);
    } else {
      createChatMutation.mutate();
    }
  };

  if (!document) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" message="Loading document..." />
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen flex flex-col bg-gray-50">
        <Header
          title={document.original_filename}
          showBack
          backHref="/upload"
          actions={
            <>
              <button
                onClick={handleChatClick}
                disabled={!isReady || createChatMutation.isPending}
                className="px-4 py-2 text-body-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {chatOpen ? 'Close Chat' : 'Chat'}
              </button>
              <button
                onClick={handleCompareClick}
                disabled={!isReady}
                className="px-4 py-2 text-body-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Compare
              </button>
              <div className="relative">
                <button
                  onClick={handleExportClick}
                  disabled={!isReady}
                  className="px-4 py-2 text-body-sm font-medium text-white bg-primary rounded-md hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Export
                </button>
                {exportMenuOpen && (
                  <ExportMenu
                    documentId={documentId}
                    onClose={() => setExportMenuOpen(false)}
                  />
                )}
              </div>
            </>
          }
        />

        <div className="flex-1 flex">
          {/* Sidebar */}
          <aside className="w-60 bg-gray-50 border-r border-gray-200 p-4 space-y-2">
            <h3 className="text-body-sm font-semibold text-gray-900 mb-3">Contents</h3>
            
            <button
              onClick={() => setActiveTab('simplified')}
              disabled={!isReady}
              className={`
                w-full text-left px-3 py-2 text-body-sm rounded-md transition-colors
                ${activeTab === 'simplified'
                  ? 'bg-white border-l-4 border-primary text-gray-900 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
                }
                disabled:opacity-50 disabled:cursor-not-allowed
              `}
            >
              Summary
            </button>
            
            <button
              onClick={() => setActiveTab('clauses')}
              disabled={!isReady}
              className={`
                w-full text-left px-3 py-2 text-body-sm rounded-md transition-colors
                ${activeTab === 'clauses'
                  ? 'bg-white border-l-4 border-primary text-gray-900 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
                }
                disabled:opacity-50 disabled:cursor-not-allowed
              `}
            >
              Clauses ({clauses.length})
            </button>
            
            <button
              onClick={() => setActiveTab('original')}
              disabled={!isReady}
              className={`
                w-full text-left px-3 py-2 text-body-sm rounded-md transition-colors
                ${activeTab === 'original'
                  ? 'bg-white border-l-4 border-primary text-gray-900 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
                }
                disabled:opacity-50 disabled:cursor-not-allowed
              `}
            >
              Original
            </button>
          </aside>

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto">
            <div className="max-w-4xl mx-auto p-8">
              {/* Processing State */}
              {isProcessing && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
                  <LoadingSpinner />
                  <p className="mt-4 text-body font-medium text-blue-900">
                    Processing Document
                  </p>
                  {processingStage && (
                    <p className="mt-2 text-body-sm text-blue-700">
                      Stage: {processingStage.replace(/_/g, ' ')}
                    </p>
                  )}
                </div>
              )}

              {/* Failed State */}
              {isFailed && (
                <ErrorAlert
                  title="Processing Failed"
                  message={failureReason || 'Document processing failed'}
                  onRetry={() => router.push('/upload')}
                />
              )}

              {/* Ready State */}
              {isReady && (
                <>
                  {/* Tab: Simplified */}
                  {activeTab === 'simplified' && (
                    <div className="space-y-6">
                      <header>
                        <h2 className="text-title mb-2">Plain-Language Summary</h2>
                        <p className="text-body-sm text-gray-600">
                          {document.page_count} pages · Auto-simplified at plain English reading level
                        </p>
                      </header>

                      {simplifyMutation.isPending || !simplification ? (
                        <LoadingSpinner message="Generating simplified version..." />
                      ) : simplifyMutation.isError ? (
                        <ErrorAlert
                          message="Failed to generate simplification"
                          onRetry={() => simplifyMutation.mutate()}
                        />
                      ) : (
                        <>
                          <div className="prose prose-gray max-w-none">
                            <div className="bg-white rounded-lg border border-gray-200 p-6">
                              <div className="text-body leading-relaxed whitespace-pre-line">
                                {simplification.simplified_text}
                              </div>
                            </div>
                          </div>

                          {simplification.citations && simplification.citations.length > 0 && (
                            <div className="mt-6">
                              <h3 className="text-heading mb-3">Citations</h3>
                              <div className="space-y-2">
                                {simplification.citations.map((citation, idx) => (
                                  <button
                                    key={citation.chunk_id}
                                    onClick={() => handleCitationClick(citation)}
                                    className="
                                      w-full text-left p-3 bg-gray-50 rounded-sm
                                      border-l-4 border-primary
                                      hover:bg-gray-100 transition-colors
                                    "
                                  >
                                    <p className="text-body-sm text-gray-900">
                                      <sup className="font-semibold text-primary mr-1">{idx + 1}</sup>
                                      Page {citation.page_number}: &ldquo;{citation.excerpt}&rdquo;
                                    </p>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}

                  {/* Tab: Original */}
                  {activeTab === 'original' && (
                    <div className="space-y-6" ref={originalContentRef}>
                      <header>
                        <h2 className="text-title mb-2">Original Document</h2>
                        <p className="text-body-sm text-gray-600">
                          Extracted text · {document.page_count} pages
                        </p>
                      </header>

                      <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-200">
                        {document.chunks && document.chunks.map((chunk) => (
                          <div
                            key={chunk.id}
                            id={`chunk-${chunk.id}`}
                            className={`
                              p-6 transition-all duration-300
                              ${highlightedChunkId === chunk.id 
                                ? 'bg-yellow-100 animate-pulse' 
                                : 'bg-white'
                              }
                            `}
                          >
                            <div className="flex items-start gap-4">
                              <span className="text-caption text-gray-500 font-mono flex-shrink-0">
                                Page {chunk.page_number}
                              </span>
                              <p className="text-body text-gray-900 whitespace-pre-wrap flex-1">
                                {chunk.text}
                              </p>
                            </div>
                          </div>
                        ))}
                        {!document.chunks || document.chunks.length === 0 && (
                          <div className="p-6 font-mono text-sm">
                            <p className="text-gray-700 whitespace-pre-wrap">
                              [Original document text would appear here]
                              {'\n\n'}
                              This requires fetching the full extracted text from the backend.
                              {'\n'}
                              In production, this would show the complete document content
                              {'\n'}
                              with line numbers and highlighted sections for citations.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Tab: Clauses */}
                  {activeTab === 'clauses' && (
                    <div className="space-y-6">
                      <header className="flex items-center justify-between">
                        <div>
                          <h2 className="text-title mb-2">Extracted Clauses</h2>
                          <p className="text-body-sm text-gray-600">
                            {clauses.length} clauses identified with risk assessment
                          </p>
                        </div>
                        
                        <select className="px-3 py-2 text-body-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary">
                          <option>All types</option>
                          <option>Indemnification</option>
                          <option>Termination</option>
                          <option>Auto-renewal</option>
                          <option>Payment terms</option>
                        </select>
                      </header>

                      {clausesLoading ? (
                        <LoadingSpinner message="Loading clauses..." />
                      ) : clauses.length === 0 ? (
                        <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                          <p className="text-body text-gray-600">No clauses extracted yet</p>
                        </div>
                      ) : (
                        <div className="grid gap-4 sm:grid-cols-2">
                          {clauses.map((clause) => (
                            <ClauseCard
                              key={clause.id}
                              clauseType={clause.clause_type}
                              textExcerpt={clause.text_excerpt}
                              riskLevel={clause.risk_level}
                              riskRationale={clause.risk_rationale}
                              onClick={() => {
                                setActiveTab('original');
                                // TODO: Scroll to clause location
                              }}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </main>

          {/* Chat Pane */}
          {chatOpen && chatSessionId && (
            <div className="w-96 flex-shrink-0">
              <ChatPane
                documentId={documentId}
                documentName={document.original_filename}
                messages={chatSession.messages}
                isStreaming={chatSession.isSendingMessage}
                onSendMessage={(content) => chatSession.sendMessage(content)}
                onCitationClick={handleCitationClick}
                onClose={() => setChatOpen(false)}
              />
            </div>
          )}
        </div>

        <DisclaimerFooter />
      </div>
    </ProtectedRoute>
  );
}
