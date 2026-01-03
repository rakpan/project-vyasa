"use client"

/**
 * Hook for managing ingestion jobs
 * Polls job status and manages per-file state
 */

import { useState, useEffect, useCallback, useRef } from "react"
import type { IngestionStatus } from "@/components/ingestion-card"

export interface IngestionJob {
  id: string // ingestion_id (source of truth)
  filename: string
  jobId: string | null
  status: IngestionStatus
  progress: number
  error?: string
  firstGlance?: {
    pages: number
    tables_detected: number
    figures_detected: number
    text_density: number
  }
  confidence?: "High" | "Medium" | "Low"
  createdAt: number
}

interface UseIngestionJobsOptions {
  projectId: string
  pollingInterval?: number // milliseconds
}

// Map backend JobStatus to IngestionStatus
function mapJobStatusToIngestionStatus(
  backendStatus: string,
  currentStep?: string
): IngestionStatus {
  switch (backendStatus) {
    case "QUEUED":
    case "PENDING":
      return "Queued"
    case "RUNNING":
    case "PROCESSING":
      // Map based on current_step
      if (currentStep === "cartographer" || currentStep?.toLowerCase().includes("extract")) {
        return "Extracting"
      }
      if (currentStep === "vision" || currentStep?.toLowerCase().includes("vision")) {
        return "Mapping"
      }
      if (currentStep === "critic" || currentStep?.toLowerCase().includes("critic")) {
        return "Verifying"
      }
      return "Extracting" // Default for RUNNING
    case "SUCCEEDED":
    case "COMPLETED":
      return "Completed"
    case "FAILED":
      return "Failed"
    default:
      return "Queued"
  }
}

export function useIngestionJobs({ projectId, pollingInterval = 2000 }: UseIngestionJobsOptions) {
  const [jobs, setJobs] = useState<IngestionJob[]>([])
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  // Poll ingestion status (source of truth)
  const pollIngestionStatus = useCallback(async (ingestionId: string) => {
    try {
      const response = await fetch(
        `/api/proxy/orchestrator/api/projects/${projectId}/ingest/${ingestionId}/status`
      )
      if (!response.ok) {
        throw new Error(`Failed to fetch ingestion status: ${response.status}`)
      }

      const data = await response.json()
      // Response format: { ingestion_id, state, progress_pct, error_message, first_glance, confidence, job_id }
      const status = (data.state || "Queued") as IngestionStatus
      const progress = data.progress_pct !== undefined ? data.progress_pct : 0
      const error = data.error_message || undefined
      const firstGlance = data.first_glance
      const confidence = data.confidence as "High" | "Medium" | "Low" | undefined
      const jobId = data.job_id || null

      setJobs((prev) =>
        prev.map((j) =>
          j.id === ingestionId
            ? {
                ...j,
                status,
                progress,
                error,
                firstGlance,
                confidence,
                jobId: jobId || j.jobId, // Preserve existing jobId if not provided
              }
            : j
        )
      )

      // Return whether to continue polling
      return status !== "Completed" && status !== "Failed"
    } catch (error) {
      console.error("Failed to poll ingestion status:", error)
      // Continue polling on error (might be transient)
      return true
    }
  }, [projectId])

  // Start polling for an ingestion (using ingestion_id as source of truth)
  const startPolling = useCallback(
    (ingestionId: string) => {
      // Poll immediately
      pollIngestionStatus(ingestionId).then((shouldContinue) => {
        if (!shouldContinue) return

        // Then poll at interval
        const intervalId = setInterval(async () => {
          // Check current ingestion state
          setJobs((currentJobs) => {
            const job = currentJobs.find((j) => j.id === ingestionId)
            if (!job) {
              clearInterval(intervalId)
              return currentJobs
            }

            // Only poll if still active
            if (job.status === "Queued" || job.status === "Extracting" || job.status === "Mapping" || job.status === "Verifying") {
              pollIngestionStatus(ingestionId).then((continuePolling) => {
                if (!continuePolling) {
                  clearInterval(intervalId)
                }
              })
            } else {
              // Ingestion completed or failed, stop polling
              clearInterval(intervalId)
            }

            return currentJobs
          })
        }, pollingInterval)

        // Store interval ID for cleanup
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
        }
        pollingRef.current = intervalId
      })
    },
    [pollIngestionStatus, pollingInterval]
  )

  // Add a new ingestion job (ingestion_id is the source of truth)
  const addJob = useCallback(
    (filename: string, ingestionId: string | null = null) => {
      // Generate temporary ID if ingestion_id not provided yet
      const id = ingestionId || `ingestion-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
      const newJob: IngestionJob = {
        id,
        filename,
        jobId: null,
        status: "Queued",
        progress: 0,
        createdAt: Date.now(),
      }

      setJobs((prev) => [...prev, newJob])

      // Start polling immediately (will update when job_id is set)
      startPolling(id)

      return id
    },
    [startPolling]
  )

  // Update job with jobId and ingestionId (when workflow starts)
  const updateJobId = useCallback((ingestionId: string, jobId: string) => {
    setJobs((prev) =>
      prev.map((j) =>
        j.id === ingestionId
          ? { ...j, jobId, status: "Queued" }
          : j
      )
    )

    // Continue polling (already started in addJob)
    // Polling will pick up the job_id from the status endpoint
  }, [])

  // Remove a job
  const removeJob = useCallback((ingestionId: string) => {
    setJobs((prev) => prev.filter((j) => j.id !== ingestionId))
  }, [])

  // Retry a failed job (resets status, parent component handles re-upload)
  const retryJob = useCallback(
    (ingestionId: string) => {
      setJobs((prev) =>
        prev.map((j) =>
          j.id === ingestionId
            ? {
                ...j,
                status: "Queued" as IngestionStatus,
                progress: 0,
                error: undefined,
              }
            : j
        )
      )
    },
    []
  )

  // Update job status directly (for error handling)
  const updateJobStatus = useCallback(
    (ingestionId: string, status: IngestionStatus, error?: string) => {
      setJobs((prev) =>
        prev.map((j) =>
          j.id === ingestionId
            ? {
                ...j,
                status,
                error,
              }
            : j
        )
      )
    },
    []
  )

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [])

  const activeJobs = jobs.filter(
    (j) =>
      j.status === "Queued" ||
      j.status === "Extracting" ||
      j.status === "Mapping" ||
      j.status === "Verifying"
  )

  return {
    jobs,
    activeJobs,
    addJob,
    updateJobId,
    removeJob,
    retryJob,
    updateJobStatus,
  }
}

