"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { createAbortableFetch, createIsMountedRef, startPolling } from "@/lib/async"

type JobStatusResponse = {
  status: "running" | "completed" | "failed" | string
  progress: number
  step: string
  error?: string | null
}

type JobProgressProps = {
  jobId: string
  onComplete?: () => void
}

export function JobProgress({ jobId, onComplete }: JobProgressProps) {
  const [status, setStatus] = useState<JobStatusResponse | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return

    // Track component mount status to prevent setState after unmount
    const mountedRef = createIsMountedRef()

    // Start polling with proper cleanup
    const pollingController = startPolling({
      intervalMs: 2000,
      immediate: true,
      fn: async (signal) => {
        try {
          // Use abortable fetch to ensure cancellation on unmount
          const { promise } = createAbortableFetch<JobStatusResponse>(
            `/jobs/${jobId}/status`,
            { signal }
          )

          const json = await promise

          // Only update state if component is still mounted
          if (mountedRef.isMounted()) {
            setStatus(json)
            setFetchError(null)
            if (json.status === "completed" && onComplete) {
              onComplete()
            }
          }
        } catch (err) {
          // Ignore AbortError (expected when stopping)
          if (err instanceof Error && err.name === "AbortError") {
            return
          }

          // Only update error state if component is still mounted
          if (mountedRef.isMounted()) {
            setFetchError(
              err instanceof Error ? err.message : "Failed to fetch job status"
            )
          }
        }
      },
      onError: (error) => {
        // Error handler only called for non-abort errors
        if (mountedRef.isMounted() && error.name !== "AbortError") {
          setFetchError(error.message || "Failed to fetch job status")
        }
      },
    })

    // Cleanup: mark as unmounted and stop polling
    return () => {
      mountedRef.unmount()
      pollingController.stop("Component unmounted")
    }
  }, [jobId, onComplete])

  const progressValue = status?.progress ?? 0
  const stepLabel = status?.step ?? "Initializing..."
  const isFailed = status?.status === "failed"
  const isRunning = status?.status === "running"

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-muted-foreground">
          Step: <span className="text-foreground">{stepLabel}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          {isRunning && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          <span className="font-semibold">{progressValue}%</span>
        </div>
      </div>

      <Progress value={progressValue} />

      {isFailed && status?.error && (
        <Alert variant="destructive">
          <AlertTitle>Job failed</AlertTitle>
          <AlertDescription>{status.error}</AlertDescription>
        </Alert>
      )}

      {fetchError && (
        <Alert variant="destructive">
          <AlertTitle>Status error</AlertTitle>
          <AlertDescription>{fetchError}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}
