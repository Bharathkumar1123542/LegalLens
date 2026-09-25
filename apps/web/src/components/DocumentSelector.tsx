import React, { useState } from 'react';
import type { Document } from '@/types';
import { formatFileSize, formatRelativeTime } from '@/lib/utils';

interface DocumentSelectorProps {
  documents: Document[];
  selectedIds: string[];
  onSelectionChange: (selectedIds: string[]) => void;
  minSelection?: number;
  maxSelection?: number;
}

export function DocumentSelector({
  documents,
  selectedIds,
  onSelectionChange,
  minSelection = 2,
  maxSelection = 5,
}: DocumentSelectorProps) {
  const handleToggle = (documentId: string) => {
    const isSelected = selectedIds.includes(documentId);
    
    if (isSelected) {
      // Deselect
      onSelectionChange(selectedIds.filter((id) => id !== documentId));
    } else {
      // Select (if under max limit)
      if (selectedIds.length < maxSelection) {
        onSelectionChange([...selectedIds, documentId]);
      }
    }
  };

  const readyDocuments = documents.filter((doc) => doc.status === 'ready');
  const canSelect = selectedIds.length < maxSelection;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-body-sm text-gray-600">
          Select {minSelection}–{maxSelection} documents to compare
        </p>
        <span className="text-body-sm font-medium text-gray-900">
          {selectedIds.length} / {maxSelection} selected
        </span>
      </div>

      {readyDocuments.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <p className="text-body text-gray-600">No documents available</p>
          <p className="text-body-sm text-gray-500 mt-1">
            Upload and process documents before comparing
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-200">
          {readyDocuments.map((doc) => {
            const isSelected = selectedIds.includes(doc.id);
            const isDisabled = !isSelected && !canSelect;

            return (
              <label
                key={doc.id}
                className={`
                  flex items-center gap-4 px-4 py-4 cursor-pointer
                  transition-colors
                  ${isSelected
                    ? 'bg-primary-50'
                    : isDisabled
                    ? 'opacity-50 cursor-not-allowed'
                    : 'hover:bg-gray-50'
                  }
                `}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => handleToggle(doc.id)}
                  disabled={isDisabled}
                  className="
                    h-5 w-5 rounded border-gray-300
                    text-primary focus:ring-primary
                    disabled:cursor-not-allowed
                  "
                />

                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <svg className="w-8 h-8 text-gray-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
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

                {isSelected && (
                  <span className="flex-shrink-0 px-2 py-1 text-caption font-medium text-primary bg-primary-50 rounded">
                    Selected
                  </span>
                )}
              </label>
            );
          })}
        </div>
      )}

      {selectedIds.length > 0 && selectedIds.length < minSelection && (
        <p className="text-body-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3">
          Select at least {minSelection} documents to start comparison
        </p>
      )}
    </div>
  );
}
