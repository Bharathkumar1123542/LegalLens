/**
 * useDocumentStatus hook
 * Polls document processing status until ready or failed
 */

import { useQuery } from '@tanstack/react-query';
import { getDocumentStatus } from '@/lib/api-client';
import type { Document } from '@/types';

interface UseDocumentStatusOptions {
  documentId: string;
  enabled?: boolean;
  refetchInterval?: number | false;
}

export function useDocumentStatus({
  documentId,
  enabled = true,
  refetchInterval,
}: UseDocumentStatusOptions) {
  const query = useQuery<Document>({
    queryKey: ['document', documentId, 'status'],
    queryFn: () => getDocumentStatus(documentId),
    enabled,
    refetchInterval: (query) => {
      // Auto-polling logic: poll every 2s while processing
      const data = query.state.data;
      if (!data) return false;
      if (data.status === 'processing' || data.status === 'uploaded') {
        return refetchInterval ?? 2000;
      }
      return false; // Stop polling when ready or failed
    },
  });

  const isProcessing = query.data?.status === 'processing' || query.data?.status === 'uploaded';
  const isReady = query.data?.status === 'ready';
  const isFailed = query.data?.status === 'failed';

  return {
    ...query,
    document: query.data,
    isProcessing,
    isReady,
    isFailed,
    processingStage: query.data?.processing_stage,
    failureReason: query.data?.failure_reason,
  };
}
