"use client"

/**
 * Global Status Banner Component
 * Shows when any ingestion/job is active
 * Displays current phase summary with optional "View details" link
 */

import { useMemo } from "react"
import { Activity, X, ExternalLink } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { IngestionStatus } from "./ingestion-card"

interface ActiveJob {
  jobId: string
  filename: string
  status: IngestionStatus
  progress?: number
}

interface GlobalStatusBannerProps {
  activeJobs: ActiveJob[]
  onDismiss?: () => void
  onViewDetails?: (jobId: string) => void
  className?: string
}

export function GlobalStatusBanner({
  activeJobs,
  onDismiss,
  onViewDetails,
  className,
}: GlobalStatusBannerProps) {
  const hasActiveJobs = activeJobs.length > 0

  const summary = useMemo(() => {
    if (activeJobs.length === 0) return null

    const statusCounts = activeJobs.reduce((acc, job) => {
      acc[job.status] = (acc[job.status] || 0) + 1
      return acc
    }, {} as Record<IngestionStatus, number>)

    const parts: string[] = []
    if (statusCounts.Extracting) parts.push(`${statusCounts.Extracting} extracting`)
    if (statusCounts.Mapping) parts.push(`${statusCounts.Mapping} mapping`)
    if (statusCounts.Verifying) parts.push(`${statusCounts.Verifying} verifying`)
    if (statusCounts.Queued) parts.push(`${statusCounts.Queued} queued`)

    if (parts.length === 0) return null

    return parts.join(", ")
  }, [activeJobs])

  if (!hasActiveJobs) return null

  const primaryJob = activeJobs[0]
  const isProcessing = primaryJob.status === "Extracting" || primaryJob.status === "Mapping" || primaryJob.status === "Verifying"

  return (
    <Alert
      className={cn(
        "border-primary/50 bg-primary/5 rounded-lg shadow-sm",
        className
      )}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Activity className={cn(
            "h-5 w-5 text-primary flex-shrink-0",
            isProcessing && "animate-pulse"
          )} />

          <div className="flex-1 min-w-0">
            <AlertTitle className="text-sm font-semibold">
              Processing {activeJobs.length} {activeJobs.length === 1 ? "file" : "files"}
            </AlertTitle>
            {summary && (
              <AlertDescription className="text-xs text-muted-foreground mt-1">
                {summary}
              </AlertDescription>
            )}
          </div>

          {activeJobs.length > 1 && (
            <Badge variant="secondary" className="text-xs flex-shrink-0">
              +{activeJobs.length - 1} more
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {onViewDetails && primaryJob.jobId && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onViewDetails(primaryJob.jobId)}
              className="text-xs"
            >
              <ExternalLink className="h-3 w-3 mr-1" />
              View details
            </Button>
          )}

          {onDismiss && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDismiss}
              className="text-xs h-7 w-7 p-0"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </Alert>
  )
}

