/**
 * React hook for polling workflow job status.
 * 
 * Usage:
 *   const { status, isLoading, error, poll } = useJobPoll();
 *   
 *   // Start polling
 *   poll(jobId, (status) => {
 *     console.log(`Progress: ${status.progress * 100}%`);
 *   });
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { JobStatus, pollWorkflowStatus } from '@/lib/orchestrator-client';

export interface UseJobPollReturn {
  status: JobStatus | null;
  isLoading: boolean;
  error: string | null;
  poll: (jobId: string, onUpdate?: (status: JobStatus) => void) => Promise<void>;
  reset: () => void;
}

export function useJobPoll(): UseJobPollReturn {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const poll = useCallback(async (
    jobId: string,
    onUpdate?: (status: JobStatus) => void
  ) => {
    // Cancel any existing polling
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setIsLoading(true);
    setError(null);
    setStatus(null);

    try {
      const finalStatus = await pollWorkflowStatus(
        jobId,
        (update) => {
          setStatus(update);
          if (onUpdate) {
            onUpdate(update);
          }
        },
        2000, // Poll every 2 seconds
        5 * 60 * 1000 // Max 5 minutes
      );

      setStatus(finalStatus);
      setIsLoading(false);

      if (finalStatus.status === 'FAILED') {
        setError(finalStatus.error || 'Job failed');
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Polling was cancelled, ignore
        return;
      }
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setStatus(null);
    setIsLoading(false);
    setError(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    status,
    isLoading,
    error,
    poll,
    reset,
  };
}

