"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Checkbox } from "@/components/ui/checkbox"
import { Loader2, RefreshCw, CheckCircle2, XCircle, Clock, Link2 } from "lucide-react"
import { toast } from "@/hooks/use-toast"
import { useRouter } from "next/navigation"

interface JobStatusCardProps {
  jobId: string
  projectId: string
  status?: string
  onStatusChange?: (status: string) => void
}

interface ExternalReference {
  reference_id: string
  source_name: string
  source_url?: string
  extracted_at: string
  status: string
  tags: string[]
}

interface JobStatusResponse {
  status: string
  progress: number
  step: string
  error?: string
  parent_job_id?: string
  version?: number
}

export function JobStatusCard({ jobId, projectId, status: initialStatus, onStatusChange }: JobStatusCardProps) {
  const router = useRouter()
  const [jobStatus, setJobStatus] = useState<JobStatusResponse | null>(null)
  const [showReprocessModal, setShowReprocessModal] = useState(false)
  const [references, setReferences] = useState<ExternalReference[]>([])
  const [selectedReferenceIds, setSelectedReferenceIds] = useState<Set<string>>(new Set())
  const [loadingReferences, setLoadingReferences] = useState(false)
  const [reprocessing, setReprocessing] = useState(false)

  useEffect(() => {
    if (!jobId) return

    const fetchStatus = async () => {
      try {
        const response = await fetch(`/api/proxy/orchestrator/jobs/${jobId}/status`)
        if (response.ok) {
          const data = await response.json()
          setJobStatus(data)
          onStatusChange?.(data.status)
        }
      } catch (err) {
        console.error("Failed to fetch job status:", err)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 2000)
    return () => clearInterval(interval)
  }, [jobId, onStatusChange])

  const loadReferences = async () => {
    setLoadingReferences(true)
    try {
      const response = await fetch(
        `/api/proxy/orchestrator/api/knowledge/references?project_id=${projectId}`
      )
      if (response.ok) {
        const data = await response.json()
        // Filter to only EXTRACTED or PROMOTED references
        const filtered = (data || []).filter(
          (ref: ExternalReference) => ref.status === "EXTRACTED" || ref.status === "PROMOTED"
        )
        setReferences(filtered)
      }
    } catch (err) {
      toast({
        title: "Failed to load references",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      })
    } finally {
      setLoadingReferences(false)
    }
  }

  const handleOpenReprocess = () => {
    setShowReprocessModal(true)
    loadReferences()
  }

  const handleSelectReference = (referenceId: string, checked: boolean) => {
    const newSelected = new Set(selectedReferenceIds)
    if (checked) {
      newSelected.add(referenceId)
    } else {
      newSelected.delete(referenceId)
    }
    setSelectedReferenceIds(newSelected)
  }

  const handleReprocess = async () => {
    if (selectedReferenceIds.size === 0) {
      toast({
        title: "No references selected",
        description: "Please select at least one reference to include.",
        variant: "destructive",
      })
      return
    }

    setReprocessing(true)
    try {
      const response = await fetch(`/api/proxy/orchestrator/jobs/${jobId}/reprocess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reference_ids: Array.from(selectedReferenceIds),
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Reprocess failed: ${response.statusText}`)
      }

      const result = await response.json()
      
      // Get original job to retrieve pdfUrl, fallback to project seed file
      let pdfUrlParam = ""
      try {
        const jobResponse = await fetch(`/api/proxy/orchestrator/jobs/${jobId}/status`)
        if (jobResponse.ok) {
          const jobData = await jobResponse.json()
          const pdfPath =
            jobData.pdf_url ||
            jobData.pdfUrl ||
            jobData.pdf_path ||
            jobData?.result?.pdf_path ||
            jobData?.initial_state?.pdf_path
          if (pdfPath) {
            const built = `/api/proxy/orchestrator/files/${encodeURIComponent(pdfPath)}`
            pdfUrlParam = `&pdfUrl=${encodeURIComponent(built)}`
          }
        }
        // If still missing, attempt to pull the first seed file from project
        if (!pdfUrlParam) {
          const projectResp = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}`)
          if (projectResp.ok) {
            const project = await projectResp.json()
            const seedPdf = (project.seed_files || []).find((f: string) => f.toLowerCase().endsWith(".pdf"))
            if (seedPdf) {
              const built = `/api/proxy/orchestrator/files/${encodeURIComponent(seedPdf)}`
              pdfUrlParam = `&pdfUrl=${encodeURIComponent(built)}`
            }
          }
        }
      } catch (err) {
        console.warn("Failed to retrieve pdfUrl for reprocess:", err)
      }
      
      toast({
        title: "Reprocessing started",
        description: `New job ${result.job_id.substring(0, 8)}... created.`,
      })

      // Navigate to new job with pdfUrl if available
      router.push(`/research-workbench?jobId=${result.job_id}&projectId=${projectId}${pdfUrlParam}`)
      setShowReprocessModal(false)
    } catch (err) {
      toast({
        title: "Reprocess failed",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      })
    } finally {
      setReprocessing(false)
    }
  }

  const currentStatus = jobStatus?.status || initialStatus || "unknown"
  const statusLower = currentStatus.toLowerCase()
  
  // Case-insensitive status check for reprocess eligibility
  const canReprocess = ["completed", "low_confidence", "conflicts_present", "succeeded", "finalized"].includes(statusLower)
  
  const version = jobStatus?.version || 1
  const parentJobId = jobStatus?.parent_job_id

  const getStatusIcon = () => {
    switch (statusLower) {
      case "completed":
      case "succeeded":
      case "finalized":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "running":
      case "processing":
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />
    }
  }

  const getStatusBadge = () => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      completed: "default",
      succeeded: "default",
      finalized: "default",
      failed: "destructive",
      running: "secondary",
      processing: "secondary",
    }
    return (
      <Badge variant={variants[statusLower] || "outline"} className="flex items-center gap-1">
        {getStatusIcon()}
        {currentStatus}
      </Badge>
    )
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                Job Status
                {version > 1 && (
                  <Badge variant="outline" className="text-xs">
                    v{version}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription className="mt-1">
                {jobId.substring(0, 8)}...
                {parentJobId && (
                  <span className="ml-2 flex items-center gap-1 text-xs">
                    <Link2 className="h-3 w-3" />
                    Parent: {parentJobId.substring(0, 8)}...
                  </span>
                )}
              </CardDescription>
            </div>
            {getStatusBadge()}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {jobStatus && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Step:</span>
                <span className="font-medium">{jobStatus.step || "Unknown"}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Progress:</span>
                <span className="font-medium">{jobStatus.progress || 0}%</span>
              </div>
              {jobStatus.error && (
                <div className="rounded-md bg-destructive/10 p-2 text-sm text-destructive">
                  {jobStatus.error}
                </div>
              )}
            </div>
          )}

          {canReprocess && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleOpenReprocess}
              className="w-full flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Reprocess with New Knowledge
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Reprocess Modal */}
      <Dialog open={showReprocessModal} onOpenChange={setShowReprocessModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Reprocess with New Knowledge</DialogTitle>
            <DialogDescription>
              Select external references to include in reprocessing. Promoted facts from these references will be used to augment extraction.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 max-h-[400px] overflow-y-auto">
            {loadingReferences ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : references.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                No extracted references available for this project.
              </div>
            ) : (
              <div className="space-y-2">
                {references.map((ref) => (
                  <div
                    key={ref.reference_id}
                    className="flex items-start gap-3 p-3 rounded-md border border-border hover:bg-muted/50"
                  >
                    <Checkbox
                      checked={selectedReferenceIds.has(ref.reference_id)}
                      onCheckedChange={(checked) =>
                        handleSelectReference(ref.reference_id, checked as boolean)
                      }
                    />
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{ref.source_name}</span>
                        <Badge variant="outline" className="text-xs">
                          {ref.status}
                        </Badge>
                      </div>
                      {ref.source_url && (
                        <a
                          href={ref.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-primary hover:underline"
                        >
                          {ref.source_url}
                        </a>
                      )}
                      <div className="flex flex-wrap gap-1">
                        {ref.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {new Date(ref.extracted_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowReprocessModal(false)}
              disabled={reprocessing}
            >
              Cancel
            </Button>
            <Button
              onClick={handleReprocess}
              disabled={reprocessing || selectedReferenceIds.size === 0}
              className="flex items-center gap-2"
            >
              {reprocessing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Reprocessing...
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4" />
                  Reprocess ({selectedReferenceIds.size})
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
