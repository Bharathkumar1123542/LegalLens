'use client';

import React from 'react';
import type { DocumentStatus } from '@/types';

interface UploadProgressBarProps {
  status: DocumentStatus;
  progress?: number;
}

interface Stage {
  id: 'uploaded' | 'processing' | 'ready';
  label: string;
  progressRange: [number, number];
}

const STAGES: Stage[] = [
  { id: 'uploaded', label: 'Uploading', progressRange: [0, 30] },
  { id: 'processing', label: 'Extracting & analyzing', progressRange: [30, 90] },
  { id: 'ready', label: 'Finalizing', progressRange: [90, 100] },
];

export function UploadProgressBar({ status, progress }: UploadProgressBarProps) {
  // Calculate overall progress based on status
  const getProgress = (): number => {
    if (progress !== undefined) return progress;

    switch (status) {
      case 'uploaded':
        return 15;
      case 'processing':
        return 60;
      case 'ready':
        return 100;
      case 'failed':
        return 0;
      default:
        return 0;
    }
  };

  const currentProgress = getProgress();
  const isComplete = status === 'ready';
  const isFailed = status === 'failed';

  // Determine which stage is active
  const getStageState = (stage: Stage): 'pending' | 'active' | 'complete' => {
    if (isComplete) return 'complete';
    if (isFailed) return 'pending';

    if (status === stage.id) return 'active';

    // Check if this stage is before the current one
    const stageIndex = STAGES.findIndex((s) => s.id === stage.id);
    const currentIndex = STAGES.findIndex((s) => s.id === status);
    
    if (currentIndex > stageIndex) return 'complete';
    return 'pending';
  };

  return (
    <div className="space-y-4">
      {/* Overall Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-body-sm">
          <span className="font-medium text-gray-900">
            {isFailed ? 'Upload failed' : isComplete ? 'Complete' : 'Processing document...'}
          </span>
          <span className="text-gray-600">{currentProgress}%</span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ease-out ${
              isFailed
                ? 'bg-red-500'
                : isComplete
                ? 'bg-green-500'
                : 'bg-primary'
            }`}
            style={{ width: `${currentProgress}%` }}
            role="progressbar"
            aria-valuenow={currentProgress}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      </div>

      {/* Stage Indicators */}
      {!isFailed && (
        <div className="space-y-3">
          {STAGES.map((stage, index) => {
            const state = getStageState(stage);
            const isActive = state === 'active';
            const isCompleted = state === 'complete';

            return (
              <div key={stage.id} className="flex items-center gap-3">
                {/* Stage Icon */}
                <div
                  className={`
                    w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-colors
                    ${isCompleted
                      ? 'bg-green-500 text-white'
                      : isActive
                      ? 'bg-primary text-white'
                      : 'bg-gray-200 text-gray-400'
                    }
                  `}
                >
                  {isCompleted ? (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <span className="text-body-sm font-semibold">{index + 1}</span>
                  )}
                </div>

                {/* Stage Label */}
                <div className="flex-1 min-w-0">
                  <p
                    className={`text-body-sm font-medium ${
                      isActive ? 'text-gray-900' : isCompleted ? 'text-green-700' : 'text-gray-500'
                    }`}
                  >
                    {stage.label}
                  </p>
                  {isActive && (
                    <div className="mt-1 flex items-center gap-2">
                      <div className="flex gap-1">
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-caption text-gray-600">In progress</span>
                    </div>
                  )}
                </div>

                {/* Stage Status */}
                {isCompleted && (
                  <span className="text-caption text-green-700 font-medium">
                    Done
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Error Message */}
      {isFailed && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-body-sm text-red-800">
            Upload failed. Please try again or contact support if the problem persists.
          </p>
        </div>
      )}
    </div>
  );
}
