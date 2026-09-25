import React, { useState, useRef, useEffect } from 'react';
import type { ChatMessage, Citation as GlobalCitation } from '@/types';

// Local Citation type for internal use (maps to global Citation)
interface Citation {
  chunkId: string;
  pageNumber: number;
  excerpt: string;
}

interface ChatPaneProps {
  documentId: string;
  documentName: string;
  messages: ChatMessage[];
  isStreaming?: boolean;
  onSendMessage: (content: string) => void;
  onCitationClick?: (citation: GlobalCitation) => void;
  onClose?: () => void;
}

export function ChatPane({
  documentName,
  messages,
  isStreaming = false,
  onSendMessage,
  onCitationClick,
  onClose,
}: ChatPaneProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isStreaming) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  return (
    <aside
      className="flex flex-col h-full bg-white border-l border-gray-200"
      aria-label="Document chat"
    >
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="flex-1 min-w-0">
          <h2 className="text-body font-semibold text-gray-900 truncate">
            Chat: {documentName}
          </h2>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-2 p-1 text-gray-500 hover:text-gray-700 rounded"
            aria-label="Close chat"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 text-body-sm mt-8">
            Ask a question about this document...
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              onCitationClick={onCitationClick}
            />
          ))
        )}
        {isStreaming && (
          <div className="flex items-center gap-2 px-4 py-3 bg-gray-100 rounded-lg max-w-[85%]">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t border-gray-200 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isStreaming}
            placeholder="Type your question..."
            className="
              flex-1 h-12 px-4 text-body-sm
              border border-gray-300 rounded-md
              focus:outline-none focus:ring-2 focus:ring-primary
              disabled:bg-gray-50 disabled:text-gray-400
            "
            aria-label="Chat message input"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="
              px-4 h-12 bg-primary text-white rounded-md
              hover:bg-primary-hover disabled:bg-gray-300
              disabled:cursor-not-allowed
              transition-colors
            "
            aria-label="Send message"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </form>

      {/* Disclaimer */}
      <footer className="px-4 py-2 bg-gray-50 border-t border-gray-200">
        <p className="text-caption text-gray-600 text-center">
          Informational only. Not legal advice.
        </p>
      </footer>
    </aside>
  );
}

function ChatMessage({
  message,
  onCitationClick,
}: {
  message: ChatMessage;
  onCitationClick?: (citation: GlobalCitation) => void;
}) {
  const isUser = message.role === 'user';
  const time = new Date(message.created_at).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`
          max-w-[85%] px-4 py-3 rounded-lg
          ${isUser
            ? 'bg-primary text-white'
            : 'bg-gray-100 text-gray-900'
          }
        `}
      >
        <div className="flex items-baseline gap-2 mb-1">
          <span className={`text-caption font-medium ${isUser ? 'text-blue-200' : 'text-gray-500'}`}>
            {isUser ? 'You' : 'Assistant'}
          </span>
          <span className={`text-caption ${isUser ? 'text-blue-300' : 'text-gray-400'}`}>
            {time}
          </span>
        </div>

        <p className="text-body-sm whitespace-pre-wrap">
          {message.content}
        </p>

        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200 space-y-1.5">
            <p className="text-caption font-medium text-gray-700">Sources:</p>
            {message.citations.map((citation, idx) => (
              <button
                key={citation.chunk_id}
                onClick={() => onCitationClick?.({
                  chunk_id: citation.chunk_id,
                  page_number: citation.page_number,
                  excerpt: citation.excerpt,
                })}
                className="
                  block w-full text-left px-2 py-1
                  text-caption text-primary hover:text-primary-hover
                  hover:bg-blue-50 rounded-sm transition-colors
                "
              >
                <sup className="font-medium">{idx + 1}</sup> Page{' '}
                {citation.page_number}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
