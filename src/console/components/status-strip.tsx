//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Play, Clock, Hash } from "lucide-react"
import { cn } from "@/lib/utils"
import { useProjectStore } from "@/state/useProjectStore"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { toast } from "@/hooks/use-toast"

interface JobStatus {
  status: string
  current_step?: string
  created_at?: string
  updated_at?: string
}

/**
 * Persistent Status Strip - Shows threadId, checkpoint time, and resume action
 * Displays in sidebar footer when a job is paused or running
 */
export function StatusStrip() {
  const router = useRouter()
  const { activeJobId, activeProjectId, activeThreadId } = useProjectStore()
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [lastCheckpoint, setLastCheckpoint] = useState<string | null>(null)

  // Fetch job status to determine if paused
  useEffect(() => {
    if (!activeJobId) {
      setJobStatus(null)
      setLastCheckpoint(null)
      return
    }

    const fetchStatus = async () => {
      try {
        const resp = await fetch(
          `/api/proxy/orchestrator/workflow/status/${activeJobId}?project_id=${activeProjectId || ""}`
        )
        if (resp.ok) {
          const data = await resp.json()
          setJobStatus(data)
          // Use updated_at as last checkpoint time
          if (data.updated_at) {
            setLastCheckpoint(data.updated_at)
          }
        }
      } catch (err) {
        console.debug("Failed to fetch job status:", err)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5000) // Poll every 5s
    return () => clearInterval(interval)
  }, [activeJobId, activeProjectId])

  const handleResume = async () => {
    if (!activeJobId || !activeProjectId) return

    setLoading(true)
    try {
      // Check if job is actually paused
      const resp = await fetch(
        `/api/proxy/orchestrator/workflow/status/${activeJobId}?project_id=${activeProjectId}`
      )
      if (!resp.ok) {
        throw new Error("Failed to check job status")
      }

      const data = await resp.json()
      if (data.status === "NEEDS_SIGNOFF") {
        // Job is paused - show interrupt panel
        toast({
          title: "Workflow paused",
          description: "Review the reframing proposal to resume.",
        })
        router.push(`/research-workbench?projectId=${activeProjectId}&jobId=${activeJobId}`)
      } else if (data.status === "RUNNING") {
        toast({
          title: "Workflow running",
          description: "The workflow is already in progress.",
        })
      } else {
        // Try to resume from checkpoint
        const resumeResp = await fetch(`/api/proxy/orchestrator/api/jobs/${activeJobId}/signoff`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "accept" }),
        })

        if (resumeResp.ok) {
          toast({
            title: "Workflow resumed",
            description: "Resuming from last checkpoint...",
          })
          router.refresh()
        } else {
          throw new Error("Failed to resume workflow")
        }
      }
    } catch (err: any) {
      toast({
        title: "Resume failed",
        description: err?.message || "Could not resume workflow",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const isPaused = jobStatus?.status === "NEEDS_SIGNOFF" || jobStatus?.status === "PAUSED"
  const isRunning = jobStatus?.status === "RUNNING"
  const showResume = isPaused && activeJobId

  if (!activeJobId && !activeThreadId) {
    return null
  }

  const formatTime = (isoString?: string) => {
    if (!isoString) return "N/A"
    try {
      const date = new Date(isoString)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)

      if (diffMins < 1) return "Just now"
      if (diffMins < 60) return `${diffMins}m ago`
      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours}h ago`
      return date.toLocaleDateString()
    } catch {
      return "N/A"
    }
  }

  return (
    <div className="border-t border-slate-200 p-2 space-y-2 bg-slate-50/50">
      {/* Thread ID */}
      {activeThreadId && (
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Hash className="h-3 w-3" />
          <span className="font-mono truncate" title={activeThreadId}>
            {activeThreadId.slice(0, 12)}...
          </span>
        </div>
      )}

      {/* Last Checkpoint Time */}
      {lastCheckpoint && (
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Clock className="h-3 w-3" />
          <span>Checkpoint: {formatTime(lastCheckpoint)}</span>
        </div>
      )}

      {/* Resume Action */}
      {showResume && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                variant="default"
                className="w-full h-7 text-xs"
                onClick={handleResume}
                disabled={loading}
              >
                <Play className="h-3 w-3 mr-1" />
                {loading ? "Resuming..." : "Resume"}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right" className="text-xs">
              Resume workflow from last checkpoint
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}

      {/* Status Badge */}
      {jobStatus && (
        <div className="flex items-center justify-center">
          <Badge
            variant="outline"
            className={cn(
              "text-[10px]",
              isPaused && "border-amber-300 text-amber-600",
              isRunning && "border-emerald-300 text-emerald-600"
            )}
          >
            {jobStatus.status}
          </Badge>
        </div>
      )}
    </div>
  )
}

