'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { createExport } from '@/lib/api-client';
import type { ExportType, ExportFormat } from '@/types';
import { LoadingSpinner } from './LoadingSpinner';

interface ExportMenuProps {
  documentId?: string;
  comparisonJobId?: string;
  onClose?: () => void;
}

interface ExportOption {
  type: ExportType;
  label: string;
  description: string;
  icon: string;
}

const EXPORT_TYPES: ExportOption[] = [
  {
    type: 'summary',
    label: 'Summary',
    description: 'Simplified overview of key points',
    icon: '📝',
  },
  {
    type: 'checklist',
    label: 'Checklist',
    description: 'Action items and requirements',
    icon: '✅',
  },
  {
    type: 'lawyer_brief',
    label: 'Lawyer Brief',
    description: 'Detailed analysis for legal review',
    icon: '⚖️',
  },
  {
    type: 'comparison_report',
    label: 'Comparison Report',
    description: 'Side-by-side document differences',
    icon: '🔍',
  },
];

const FORMATS: Array<{ format: ExportFormat; label: string; icon: string }> = [
  { format: 'pdf', label: 'PDF', icon: '📄' },
  { format: 'docx', label: 'Word', icon: '📃' },
  { format: 'md', label: 'Markdown', icon: '📝' },
];

export function ExportMenu({ documentId, comparisonJobId, onClose }: ExportMenuProps) {
  const [selectedType, setSelectedType] = useState<ExportType>('summary');
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('pdf');
  const menuRef = useRef<HTMLDivElement>(null);

  // Filter export types based on context
  const availableTypes = EXPORT_TYPES.filter((option) => {
    if (comparisonJobId) {
      return option.type === 'comparison_report';
    }
    return option.type !== 'comparison_report';
  });

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose?.();
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: () =>
      createExport({
        export_type: selectedType,
        file_format: selectedFormat,
        document_id: documentId,
        comparison_job_id: comparisonJobId,
      }),
    onSuccess: (artifact) => {
      // TODO: Poll export status and download when ready
      console.log('Export created:', artifact.id);
      alert(`Export started! ID: ${artifact.id}\n\nIn production, this would poll status and auto-download.`);
      onClose?.();
    },
  });

  const handleExport = () => {
    exportMutation.mutate();
  };

  return (
    <div
      ref={menuRef}
      className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50"
      role="dialog"
      aria-label="Export options"
    >
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-heading">Export Document</h3>
        <p className="text-caption text-gray-600 mt-1">
          Choose format and content type
        </p>
      </div>

      <div className="p-4 space-y-4">
        {/* Export Type */}
        <div>
          <label className="block text-body-sm font-medium text-gray-900 mb-2">
            Content Type
          </label>
          <div className="space-y-2">
            {availableTypes.map((option) => (
              <button
                key={option.type}
                onClick={() => setSelectedType(option.type)}
                disabled={exportMutation.isPending}
                className={`
                  w-full text-left p-3 rounded-md border-2 transition-colors
                  ${selectedType === option.type
                    ? 'border-primary bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed
                `}
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl" aria-hidden="true">
                    {option.icon}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-body-sm font-medium text-gray-900">
                      {option.label}
                    </p>
                    <p className="text-caption text-gray-600 mt-0.5">
                      {option.description}
                    </p>
                  </div>
                  {selectedType === option.type && (
                    <svg className="w-5 h-5 text-primary flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* File Format */}
        <div>
          <label className="block text-body-sm font-medium text-gray-900 mb-2">
            File Format
          </label>
          <div className="grid grid-cols-3 gap-2">
            {FORMATS.map((format) => (
              <button
                key={format.format}
                onClick={() => setSelectedFormat(format.format)}
                disabled={exportMutation.isPending}
                className={`
                  p-3 rounded-md border-2 transition-colors text-center
                  ${selectedFormat === format.format
                    ? 'border-primary bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed
                `}
              >
                <div className="text-2xl mb-1" aria-hidden="true">
                  {format.icon}
                </div>
                <div className="text-caption font-medium text-gray-900">
                  {format.label}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="p-4 border-t border-gray-200 flex items-center justify-between gap-3">
        <button
          onClick={onClose}
          disabled={exportMutation.isPending}
          className="px-4 py-2 text-body-sm font-medium text-gray-700 hover:bg-gray-100 rounded-md transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={handleExport}
          disabled={exportMutation.isPending}
          className="px-4 py-2 text-body-sm font-medium text-white bg-primary rounded-md hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {exportMutation.isPending ? (
            <>
              <LoadingSpinner size="sm" />
              <span>Exporting...</span>
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span>Export</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
