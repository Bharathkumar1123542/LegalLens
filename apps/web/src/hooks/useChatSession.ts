/**
 * useChatSession hook
 * Manages chat session lifecycle and message history
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { createChatSession, getChatMessages, sendChatMessage } from '@/lib/api-client';
import type { ChatSession, ChatMessage } from '@/types';

export function useChatSession(documentId: string, sessionId?: string) {
  const queryClient = useQueryClient();

  // Fetch existing messages
  const messagesQuery = useQuery<ChatMessage[]>({
    queryKey: ['chat', documentId, sessionId, 'messages'],
    queryFn: () => getChatMessages(documentId, sessionId!),
    enabled: !!sessionId,
  });

  // Create new session
  const createSessionMutation = useMutation({
    mutationFn: () => createChatSession(documentId),
    onSuccess: (newSession) => {
      queryClient.setQueryData<ChatSession>(['chat', documentId, newSession.id], newSession);
    },
  });

  // Send message
  const sendMessageMutation = useMutation({
    mutationFn: (content: string) => sendChatMessage(documentId, sessionId!, content),
    onSuccess: (newMessage) => {
      // Optimistically update messages list
      queryClient.setQueryData<ChatMessage[]>(
        ['chat', documentId, sessionId, 'messages'],
        (old) => [...(old || []), newMessage]
      );
    },
  });

  return {
    messages: messagesQuery.data || [],
    isLoadingMessages: messagesQuery.isLoading,
    createSession: createSessionMutation.mutate,
    isCreatingSession: createSessionMutation.isPending,
    sendMessage: sendMessageMutation.mutate,
    isSendingMessage: sendMessageMutation.isPending,
    error: messagesQuery.error || createSessionMutation.error || sendMessageMutation.error,
  };
}
