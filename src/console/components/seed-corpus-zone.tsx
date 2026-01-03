"use client"

/**
 * Seed Corpus Zone Component
 * Combines dropzone, ingestion cards, and global status banner
 * Manages ingestion state and job polling
 */

import { useState, useCallback } from "react"
import { SeedCorpusDropzone } from "./seed-corpus-dropzone"
import { IngestionCard } from "./ingestion-card"
import { GlobalStatusBanner } from "./global-status-banner"
import { DuplicateWarningModal } from "./duplicate-warning-modal"
import { useIngestionJobs } from "@/hooks/use-ingestion-jobs"
import { toast } from "@/hooks/use-toast"
import { useRouter } from "next/navigation"
import { computeFileHash } from "@/lib/file-hash"

interface SeedCorpusZoneProps {
  projectId: string
}

export function SeedCorpusZone({ projectId }: SeedCorpusZoneProps) {
  const router = useRouter()
  const { jobs, activeJobs, addJob, updateJobId, removeJob, retryJob, updateJobStatus } = useIngestionJobs({
    projectId,
    pollingInterval: 2000,
  })
  const [dismissedBanner, setDismissedBanner] = useState(false)
  const [duplicateModal, setDuplicateModal] = useState<{
    open: boolean
    filename: string
    matches: Array<{ project_id: string; project_title: string; ingested_at: string }>
    file: File
    fileHash: string
  } | null>(null)

  const handleFileSelect = useCallback(
    async (file: File) => {
      try {
        // Step 1: Compute SHA256 hash client-side
        const fileHash = await computeFileHash(file)

        // Step 2: Check for duplicates
        const duplicateCheckResponse = await fetch(
          `/api/proxy/orchestrator/api/projects/${projectId}/ingest/check-duplicate`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              sha256: fileHash,
              filename: file.name,
              size_bytes: file.size,
            }),
          }
        )

        if (!duplicateCheckResponse.ok) {
          throw new Error("Failed to check for duplicates")
        }

        const duplicateData = await duplicateCheckResponse.json()
        
        // Step 3: If duplicate, show modal
        if (duplicateData.is_duplicate && duplicateData.matches && duplicateData.matches.length > 0) {
          setDuplicateModal({
            open: true,
            filename: file.name,
            matches: duplicateData.matches,
            file,
            fileHash,
          })
          return
        }

        // Step 4: No duplicate, proceed with upload
        await proceedWithUpload(file, fileHash)
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Upload failed"
        toast({
          title: "Upload failed",
          description: errorMessage,
          variant: "destructive",
        })
      }
    },
    [projectId, addJob, updateJobId]
  )

  const proceedWithUpload = useCallback(
    async (file: File, fileHash: string) => {
      try {
        // Upload file and start workflow
        const formData = new FormData()
        formData.append("file", file)
        formData.append("project_id", projectId)

        const response = await fetch("/api/proxy/orchestrator/workflow/submit", {
          method: "POST",
          body: formData,
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.error || `Upload failed: ${response.statusText}`)
        }

        const data = await response.json()
        const jobId = data.job_id
        const returnedIngestionId = data.ingestion_id

        if (!returnedIngestionId) {
          throw new Error("No ingestion_id returned from server")
        }

        // Use ingestion_id from server response (source of truth)
        if (jobId && returnedIngestionId) {
          // Add job with real ingestion_id from server
          addJob(file.name, returnedIngestionId)
          // Update with jobId to start polling
          updateJobId(returnedIngestionId, jobId)
          toast({
            title: "File uploaded",
            description: `${file.name} is being processed.`,
          })
        } else {
          throw new Error("No job_id or ingestion_id returned from server")
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Upload failed"
        toast({
          title: "Upload failed",
          description: errorMessage,
          variant: "destructive",
        })
      }
    },
    [projectId, addJob, updateJobId]
  )

  const handleDuplicateProceed = useCallback(() => {
    if (duplicateModal) {
      proceedWithUpload(duplicateModal.file, duplicateModal.fileHash)
      setDuplicateModal(null)
    }
  }, [duplicateModal, proceedWithUpload])

  const handleDuplicateCancel = useCallback(() => {
    setDuplicateModal(null)
  }, [])

  const handleRetry = useCallback(
    async (ingestionId: string) => {
      const job = jobs.find((j) => j.id === ingestionId)
      if (!job) return

      try {
        // Call retry endpoint
        const response = await fetch(
          `/api/proxy/orchestrator/api/projects/${projectId}/ingest/${ingestionId}/retry`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
          }
        )

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.error || "Retry failed")
        }

        const data = await response.json()
        
        // Reset job status (will be updated by polling)
        retryJob(ingestionId)

        toast({
          title: "Retrying ingestion",
          description: `Retrying ${job.filename}... Please re-upload the file.`,
        })
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Retry failed"
        toast({
          title: "Retry failed",
          description: errorMessage,
          variant: "destructive",
        })
      }
    },
    [projectId, jobs, retryJob]
  )

  const handleRemove = useCallback(
    async (ingestionId: string) => {
      const job = jobs.find((j) => j.id === ingestionId)
      if (!job) return

      try {
        // Call DELETE endpoint
        const response = await fetch(
          `/api/proxy/orchestrator/api/projects/${projectId}/ingest/${ingestionId}`,
          {
            method: "DELETE",
          }
        )

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.error || "Delete failed")
        }

        // Remove from local state
        removeJob(ingestionId)
        toast({
          title: "Removed",
          description: "File removed from ingestion queue.",
        })
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Delete failed"
        toast({
          title: "Delete failed",
          description: errorMessage,
          variant: "destructive",
        })
      }
    },
    [projectId, jobs, removeJob]
  )

  const handleViewDetails = useCallback(
    (jobId: string) => {
      // Navigate to workbench with job context
      router.push(`/projects/${projectId}/workbench?jobId=${jobId}`)
    },
    [projectId, router]
  )

  const hasActiveJobs = activeJobs.length > 0 && !dismissedBanner

  return (
    <div className="space-y-4">
      {/* Duplicate Warning Modal */}
      {duplicateModal && (
        <DuplicateWarningModal
          open={duplicateModal.open}
          filename={duplicateModal.filename}
          matches={duplicateModal.matches}
          onProceed={handleDuplicateProceed}
          onCancel={handleDuplicateCancel}
        />
      )}

      {/* Global Status Banner */}
      {hasActiveJobs && (
        <GlobalStatusBanner
          activeJobs={activeJobs.map((j) => ({
            jobId: j.jobId || "",
            filename: j.filename,
            status: j.status,
            progress: j.progress,
          }))}
          onDismiss={() => setDismissedBanner(true)}
          onViewDetails={(jobId) => handleViewDetails(jobId)}
        />
      )}

      {/* Dropzone (only show if no jobs or all completed) */}
      {jobs.length === 0 && (
        <SeedCorpusDropzone
          onFileSelect={handleFileSelect}
          className="col-span-2" // Span left+center
        />
      )}

      {/* Ingestion Cards */}
      {jobs.length > 0 && (
        <div className="space-y-2">
          {jobs.map((job) => (
            <IngestionCard
              key={job.id}
              filename={job.filename}
              status={job.status}
              progress={job.progress}
              error={job.error}
              jobId={job.jobId || undefined}
              ingestionId={job.id}
              firstGlance={job.firstGlance}
              confidence={job.confidence}
              onRetry={() => handleRetry(job.id)}
              onRemove={() => handleRemove(job.id)}
              onViewDetails={job.jobId ? () => handleViewDetails(job.jobId!) : undefined}
            />
          ))}

          {/* Add more files button */}
          <SeedCorpusDropzone
            onFileSelect={handleFileSelect}
            className="mt-2"
          />
        </div>
      )}
    </div>
  )
}

