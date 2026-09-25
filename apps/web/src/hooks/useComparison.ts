/**
 * useComparison hook
 * Creates and polls comparison job until complete
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createComparison, getComparison } from '@/lib/api-client';
import type { ComparisonJob, ComparisonResult } from '@/types';

export function useComparison(comparisonJobId?: string) {
  const queryClient = useQueryClient();

  // Fetch comparison results
  const comparisonQuery = useQuery<ComparisonJob & { results?: ComparisonResult[] }>({
    queryKey: ['comparison', comparisonJobId],
    queryFn: () => getComparison(comparisonJobId!),
    enabled: !!comparisonJobId,
    refetchInterval: (query) => {
      // Poll every 3s while running
      const data = query.state.data;
      if (!data) return false;
      if (data.status === 'queued' || data.status === 'running') {
        return 3000;
      }
      return false; // Stop polling when completed or failed
    },
  });

  // Create comparison
  const createMutation = useMutation({
    mutationFn: (documentIds: string[]) => createComparison(documentIds),
    onSuccess: (job) => {
      queryClient.setQueryData(['comparison', job.id], job);
    },
  });

  const isProcessing =
    comparisonQuery.data?.status === 'queued' || comparisonQuery.data?.status === 'running';
  const isCompleted = comparisonQuery.data?.status === 'completed';
  const isFailed = comparisonQuery.data?.status === 'failed';

  return {
    comparison: comparisonQuery.data,
    results: comparisonQuery.data?.results || [],
    isLoading: comparisonQuery.isLoading,
    isProcessing,
    isCompleted,
    isFailed,
    createComparison: createMutation.mutate,
    isCreating: createMutation.isPending,
    error: comparisonQuery.error || createMutation.error,
  };
}
