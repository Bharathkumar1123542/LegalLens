'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Header } from '@/components/Header';
import { DisclaimerFooter } from '@/components/DisclaimerFooter';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { ErrorAlert } from '@/components/ErrorAlert';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { UploadProgressBar } from '@/components/UploadProgressBar';
import { useDocumentStatus } from '@/hooks/useDocumentStatus';
import { uploadDocument, listDocuments } from '@/lib/api-client';
import { validateFile, formatFileSize, formatRelativeTime } from '@/lib/utils';
import type { Document } from '@/types';

const MAX_FILE_SIZE_MB = 20;

export default function UploadPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadingDocId, setUploadingDocId] = useState<string | null>(null);

  // Poll document status if uploading
  const documentStatus = useDocumentStatus({ documentId: uploadingDocId || '' });

  // Fetch recent documents
  const { data: documents = [], isLoading: isLoadingDocs } = useQuery<Document[]>({
    queryKey: ['documents'],
    queryFn: listDocuments,
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: (document) => {
      // Start polling document status
      setUploadingDocId(document.id);
    },
    onError: (err: Error) => {
      setError(err.message || 'Upload failed');
      setUploadingDocId(null);
    },
  });

  // Navigate when document is ready
  useEffect(() => {
    if (documentStatus.isReady && uploadingDocId) {
      // Invalidate documents list
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      // Navigate to document detail
      router.push(`/document/${uploadingDocId}`);
    } else if (documentStatus.isFailed && uploadingDocId) {
      setError('Document processing failed');
      setUploadingDocId(null);
    }
  }, [documentStatus.isReady, documentStatus.isFailed, uploadingDocId, router, queryClient]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileUpload = async (file: File) => {
    setError(null);

    // Validate file
    const validation = validateFile(file);
    if (!validation.valid) {
      setError(validation.error);
      return;
    }

    // Upload via mutation
    uploadMutation.mutate(file);
  };

  const handleDocumentClick = (docId: string) => {
    router.push(`/document/${docId}`);
  };

  // Sort documents by created_at descending
  const recentDocs = documents
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  return (
    <ProtectedRoute>
      <div className="min-h-screen flex flex-col bg-gray-50">
        <Header />
        
        <main className="flex-1 px-6 py-12">
          <div className="max-w-3xl mx-auto space-y-8">
            {/* Upload Zone */}
            <div
              className={`
                relative border-2 border-dashed rounded-lg
                transition-all duration-200
                ${isDragging 
                  ? 'border-primary bg-primary-50' 
                  : 'border-gray-300 bg-white'
                }
                ${uploadMutation.isPending ? 'pointer-events-none opacity-60' : 'cursor-pointer'}
              `}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input
                type="file"
                id="file-upload"
                className="sr-only"
                accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                onChange={handleFileSelect}
                disabled={uploadMutation.isPending}
              />
              
              <label
                htmlFor="file-upload"
                className="flex flex-col items-center justify-center px-6 py-16 cursor-pointer"
              >
                {uploadingDocId && documentStatus.document?.status ? (
                  <div className="w-full max-w-md">
                    <UploadProgressBar status={documentStatus.document.status} />
                  </div>
                ) : uploadMutation.isPending ? (
                  <LoadingSpinner message="Starting upload..." />
                ) : (
                  <>
                    <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    
                    <p className="text-display text-gray-900 mb-2 text-center">
                      Drag and drop a document to begin
                    </p>
                    
                    <p className="text-body-sm text-gray-500 mb-6 text-center">
                      Supported: PDF, DOCX, TXT · Max {MAX_FILE_SIZE_MB} MB
                    </p>
                    
                    <button
                      type="button"
                      className="px-6 py-3 bg-primary text-white rounded-md font-medium hover:bg-primary-hover transition-colors"
                    >
                      Browse files
                    </button>
                  </>
                )}
              </label>
            </div>

            {/* Error */}
            {error && (
              <ErrorAlert
                message={error}
                onRetry={() => setError(null)}
              />
            )}

            {/* Recent Documents */}
            {isLoadingDocs ? (
              <div className="bg-white rounded-lg border border-gray-200 p-8">
                <LoadingSpinner message="Loading documents..." />
              </div>
            ) : recentDocs.length > 0 && (
              <section className="space-y-4">
                <h2 className="text-title">Recent Documents</h2>
                
                <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-200">
                  {recentDocs.map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => handleDocumentClick(doc.id)}
                      className="w-full px-4 py-4 text-left hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <svg className="w-5 h-5 text-gray-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                          </svg>
                          
                          <div className="flex-1 min-w-0">
                            <p className="text-body font-medium text-gray-900 truncate">
                              {doc.original_filename}
                            </p>
                            <p className="text-body-sm text-gray-500">
                              {doc.page_count && `${doc.page_count} pages · `}
                              {formatFileSize(doc.file_size_bytes)} · {formatRelativeTime(doc.created_at)}
                            </p>
                          </div>
                        </div>
                        
                        <DocumentStatusBadge status={doc.status} />
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            )}
          </div>
        </main>

        <DisclaimerFooter />
      </div>
    </ProtectedRoute>
  );
}

function DocumentStatusBadge({ status }: { status: Document['status'] }) {
  const config = {
    uploaded: { label: 'Uploaded', color: 'text-gray-600 bg-gray-100' },
    processing: { label: 'Processing', color: 'text-blue-600 bg-blue-100' },
    ready: { label: '✓ Ready', color: 'text-green-600 bg-green-100' },
    failed: { label: 'Failed', color: 'text-red-600 bg-red-100' },
  }[status];

  return (
    <span className={`px-2.5 py-1 text-caption font-medium rounded-sm ${config.color}`}>
      {config.label}
    </span>
  );
}
