"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

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
    let active = true
    if (!jobId) return

    const fetchStatus = async () => {
      try {
        const res = await fetch(`/jobs/${jobId}/status`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || "Failed to fetch job status")
        }
        const json = (await res.json()) as JobStatusResponse
        if (!active) return
        setStatus(json)
        setFetchError(null)
        if (json.status === "completed" && onComplete) {
          onComplete()
        }
      } catch (err) {
        if (!active) return
        setFetchError(err instanceof Error ? err.message : "Failed to fetch job status")
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 2000)

    return () => {
      active = false
      clearInterval(interval)
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
