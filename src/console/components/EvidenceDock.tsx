"use client"

/**
 * Evidence Dock - Left Pane (25% width)
 * Combines compact file uploader, staging area, and corpus list
 */

import { useState, useCallback, useEffect } from "react"
import { FileText, Search, Loader2, CheckCircle2, AlertCircle, AlertTriangle, Eye, X } from "lucide-react"
import { FileUploader } from "./FileUploader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { useProjectStore } from "@/state/useProjectStore"
import { VisionEnableModal } from "./vision-enable-modal"
import { getVisionOffScannedWarning } from "@/utils/ingestion-warnings"
import { VisionStatusBadge } from "./vision-status-badge"

interface IngestionStatus {
  ingestion_id: string
  status: "QUEUED" | "EXTRACTING" | "MAPPING" | "VERIFYING" | "COMPLETED" | "FAILED"
  progress: number
  metadata?: {
    pages?: number
    tables?: number
    figures?: number
    text_density?: number
  }
  error_message?: string  // Backend processing error
}

interface StagedFile {
  file: File
  ingestion_id?: string
  job_id?: string
  status?: IngestionStatus
  error?: string
  warnings?: Array<{ code: string; severity: string; message: string }>
  triage?: { likely_scanned: boolean; preview_text_chars: number; pages_previewed: number }
}

interface EvidenceDockProps {
  projectId: string
}

export function EvidenceDock({ projectId }: EvidenceDockProps) {
  const { activeProject } = useProjectStore()
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [corpusFiles, setCorpusFiles] = useState<Array<{ filename: string; claims_count?: number; status?: string; error_message?: string }>>([])
  const [visionWarning, setVisionWarning] = useState<{ filename: string; message: string } | null>(null)
  const [showVisionModal, setShowVisionModal] = useState(false)

  // Poll ingestion status
  const pollIngestionStatus = useCallback(async (ingestionId: string) => {
    try {
      const response = await fetch(
        `/api/proxy/orchestrator/api/projects/${projectId}/ingest/${ingestionId}/status`
      )
      if (!response.ok) return null
      const data = await response.json()
      
      // Normalize status defensively: handle both "status" and "state" fields, normalize to uppercase
      const rawStatus = data.status || data.state || "QUEUED"
      const normalizedStatus = typeof rawStatus === "string" ? rawStatus.toUpperCase() : "QUEUED"
      
      return {
        ingestion_id: ingestionId,
        status: normalizedStatus,
        progress: data.progress || 0,
        metadata: data.metadata,
        error_message: data.error_message,  // Include backend error message
      } as IngestionStatus
    } catch (error) {
      console.error("Failed to poll ingestion status:", error)
      return null
    }
  }, [projectId])

  // Start polling when ingestion_id is available
  useEffect(() => {
    const pollers = stagedFiles
      .filter((f) => f.ingestion_id && f.status?.status !== "COMPLETED" && f.status?.status !== "FAILED")
      .map((file) => {
        const interval = setInterval(async () => {
          if (!file.ingestion_id) return
          const status = await pollIngestionStatus(file.ingestion_id)
          if (status) {
            setStagedFiles((prev) => {
              const updated = prev.map((f) =>
                f.ingestion_id === file.ingestion_id
                  ? {
                      ...f,
                      status,
                      // Set error message immediately when status is FAILED
                      error: status.status === "FAILED" ? (status.error_message || "Processing failed") : 
                             status.status === "COMPLETED" ? undefined : f.error,
                    }
                  : f
              )
              
              // If status is COMPLETED, remove from staging queue (it will appear in corpus)
              // Keep FAILED files in queue so user can retry/remove them
              if (status.status === "COMPLETED") {
                // Remove completed file from staging queue
                return updated.filter((f) => f.ingestion_id !== file.ingestion_id)
              }
              
              return updated
            })
            
            // Reload corpus files when a file completes to show it in corpus
            if (status.status === "COMPLETED") {
              // Trigger corpus reload
              const loadCorpusFiles = async () => {
                if (!activeProject?.seed_files || activeProject.seed_files.length === 0) {
                  setCorpusFiles([])
                  return
                }
                
                try {
                  const response = await fetch(
                    `/api/proxy/orchestrator/api/projects/${projectId}/files`
                  )
                  if (response.ok) {
                    const data = await response.json()
                    const files = Array.isArray(data.files) ? data.files : []
                    setCorpusFiles(
                      files.map((f: any) => {
                        // Normalize status defensively to uppercase
                        const rawStatus = typeof f === 'object' ? f.status : "COMPLETED"
                        const normalizedStatus = typeof rawStatus === "string" ? rawStatus.toUpperCase() : "COMPLETED"
                        
                        return {
                          filename: typeof f === 'string' ? f : f.filename,
                          claims_count: typeof f === 'object' ? f.triples_count : undefined,
                          status: normalizedStatus,
                          error_message: typeof f === 'object' ? f.error_message : undefined,
                        }
                      })
                    )
                  }
                } catch (error) {
                  console.error("Failed to reload corpus files:", error)
                }
              }
              loadCorpusFiles()
            }
            
            // Stop polling if completed or failed
            if (status.status === "COMPLETED" || status.status === "FAILED") {
              clearInterval(interval)
            }
          }
        }, 2000) // Poll every 2 seconds
        return interval
      })

    return () => {
      pollers.forEach(clearInterval)
    }
  }, [stagedFiles, pollIngestionStatus, projectId, activeProject])

  // Load corpus files from project (filter ghost records)
  useEffect(() => {
    const loadCorpusFiles = async () => {
      if (!activeProject?.seed_files || activeProject.seed_files.length === 0) {
        setCorpusFiles([])
        return
      }
      
      try {
        // Fetch files from endpoint that filters ghost records
        const response = await fetch(
          `/api/proxy/orchestrator/api/projects/${projectId}/files`
        )
        if (response.ok) {
          const data = await response.json()
          const files = Array.isArray(data.files) ? data.files : []
          setCorpusFiles(
            files.map((f: any) => ({
              filename: typeof f === 'string' ? f : f.filename,
              claims_count: undefined, // TODO: Fetch from ingestion records
              status: typeof f === 'object' ? f.status : "COMPLETED",
            }))
          )
        } else {
          // Fallback: use seed_files but mark as potentially ghost records
          setCorpusFiles(
            activeProject.seed_files.map((filename) => ({
              filename,
              claims_count: undefined,
              status: "UNKNOWN", // May be ghost record
              error_message: undefined,
            }))
          )
        }
      } catch (error) {
        console.error("Failed to load corpus files:", error)
        // Fallback to seed_files
        setCorpusFiles(
          activeProject.seed_files.map((filename) => ({
            filename,
            claims_count: undefined,
            status: "UNKNOWN",
            error_message: undefined,
          }))
        )
      }
    }
    
    loadCorpusFiles()
  }, [activeProject, projectId])

  const handleFileStaged = useCallback((result: { file: File; ingestion_id: string; job_id: string; status: string; warnings?: Array<{ code: string; severity: string; message: string }>; triage?: { likely_scanned: boolean; preview_text_chars: number; pages_previewed: number } }) => {
    // If ingestion_id is already present, this is from a completed upload
    if (result.ingestion_id) {
      setStagedFiles((prev) => {
        if (prev.some((f) => f.ingestion_id === result.ingestion_id)) {
          return prev
        }
        return [
          ...prev,
          {
            file: result.file,
            ingestion_id: result.ingestion_id,
            job_id: result.job_id,
            status: {
              ingestion_id: result.ingestion_id,
              status: result.status as any,
              progress: 0,
            },
            warnings: result.warnings,
            triage: result.triage,
          },
        ]
      })
    } else {
      // Just staging the file (from compact mode)
      setStagedFiles((prev) => {
        if (prev.some((f) => f.file.name === result.file.name && f.file.size === result.file.size && !f.ingestion_id)) {
          return prev
        }
        return [...prev, { file: result.file }]
      })
    }
  }, [])

  // Pre-upload health check: verify dependencies are healthy before allowing upload
  const checkSystemHealth = useCallback(async (): Promise<{ healthy: boolean; message: string }> => {
    try {
      const response = await fetch("/api/proxy/orchestrator/health?deep=true", {
        method: "GET",
        cache: "no-store",
      })

      if (!response.ok) {
        return {
          healthy: false,
          message: "Orchestrator is unavailable. Please check system status.",
        }
      }

      const data = await response.json()

      if (data.status !== "healthy") {
        const unhealthyDeps: string[] = []
        if (data.dependencies) {
          if (data.dependencies.arango === "error") {
            unhealthyDeps.push("ArangoDB (graph database)")
          }
          if (data.dependencies.worker === "error") {
            unhealthyDeps.push("Cortex Worker (extraction service)")
          }
          if (data.dependencies.brain === "error") {
            unhealthyDeps.push("Cortex Brain (reasoning service)")
          }
        }

        const depsList = unhealthyDeps.length > 0 ? unhealthyDeps.join(", ") : "unknown services"
        return {
          healthy: false,
          message: `System dependencies are unhealthy: ${depsList}. Upload is blocked to prevent failed jobs. Please wait for services to recover or contact support.`,
        }
      }

      // Specifically check cortex-brain as it's critical for processing
      if (data.dependencies?.brain !== "ok") {
        return {
          healthy: false,
          message: "Cortex Brain service is unavailable. Upload is blocked because files cannot be processed without the reasoning service. Please wait for the service to recover.",
        }
      }

      return { healthy: true, message: "" }
    } catch (error) {
      return {
        healthy: false,
        message: "Failed to check system health. Upload is blocked to prevent failed jobs. Please try again in a moment.",
      }
    }
  }, [])

  const handleStartProcessing = async () => {
    // Pre-upload health check: block upload if dependencies are unhealthy
    const healthCheck = await checkSystemHealth()
    if (!healthCheck.healthy) {
      // Show error for all staged files
      setStagedFiles((prev) =>
        prev.map((f) => ({
          ...f,
          error: healthCheck.message,
        }))
      )
      return
    }

    for (const staged of stagedFiles.filter((f) => !f.ingestion_id)) {
      try {
        const formData = new FormData()
        formData.append("file", staged.file)
        formData.append("project_id", projectId)

        const response = await fetch("/api/proxy/orchestrator/workflow/submit", {
          method: "POST",
          body: formData,
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.error || "Upload failed")
        }

        const data = await response.json()
        const { ingestion_id, job_id, status, warnings, triage } = data
        const visionNotice = getVisionOffScannedWarning(warnings, triage)

        setStagedFiles((prev) =>
          prev.map((f) =>
            f.file === staged.file
              ? {
                  ...f,
                  ingestion_id,
                  job_id,
                  status: {
                    ingestion_id,
                    status: status || "QUEUED",
                    progress: 0,
                  },
                  // Clear any previous error on successful submission
                  error: undefined,
                  warnings,
                  triage,
                }
              : f
          )
        )

        if (visionNotice.shouldWarn) {
          setVisionWarning({
            filename: staged.file.name,
            message: visionNotice.message,
          })
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Upload failed"
        // Remove file from staging if upload fails - don't keep it as "staged"
        setStagedFiles((prev) =>
          prev.filter((f) => f.file !== staged.file)
        )
        // Show error message to user
        console.error(`Failed to upload ${staged.file.name}:`, message)
        // Optionally show a toast/notification here
      }
    }
  }

  const filteredCorpus = corpusFiles.filter((file) =>
    file.filename.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="flex flex-col h-full border-r border-slate-200">
      {/* Ingestion Zone (Top) - Compact */}
      <div className="flex-shrink-0 p-4 border-b border-slate-200">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-muted-foreground">Vision Status</span>
          <VisionStatusBadge />
        </div>
        {visionWarning && (
          <div className="mb-3 bg-amber-50 border border-amber-200 rounded-lg p-2 text-xs">
            <div className="flex items-start gap-2 mb-2">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="font-medium text-amber-900 mb-1">{visionWarning.filename}</p>
                <p className="text-amber-800">{visionWarning.message}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setVisionWarning(null)}
                className="h-5 w-5 p-0 text-amber-600 hover:text-amber-800"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowVisionModal(true)}
                className="h-6 text-xs border-amber-300 text-amber-700 hover:bg-amber-100"
              >
                <Eye className="h-3 w-3 mr-1" />
                How to enable Vision
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setVisionWarning(null)}
                className="h-6 text-xs text-amber-700 hover:text-amber-900"
              >
                Continue
              </Button>
            </div>
          </div>
        )}
        <div className="max-h-[150px] overflow-y-auto">
          <FileUploader
            projectId={projectId}
            onUploadComplete={handleFileStaged}
            compact
          />
        </div>
        <VisionEnableModal open={showVisionModal} onOpenChange={setShowVisionModal} />

        {/* Staging Area */}
        {stagedFiles.length > 0 && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="space-y-2 mb-3">
              {stagedFiles.map((staged, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-xs p-2 bg-white rounded border border-amber-200"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate font-medium">{staged.file.name}</p>
                      {staged.status?.status === "COMPLETED" && (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                      )}
                      {staged.status?.status === "FAILED" && (
                        <AlertCircle className="h-3.5 w-3.5 text-red-600 shrink-0" />
                      )}
                    </div>
                    {staged.status && (
                      <div className="mt-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge
                            variant={
                              staged.status.status === "COMPLETED"
                                ? "default"
                                : staged.status.status === "FAILED"
                                  ? "destructive"
                                  : "secondary"
                            }
                            className="text-[10px]"
                          >
                            {staged.status.status}
                          </Badge>
                          {staged.status.status === "COMPLETED" && (
                            <span className="text-emerald-700 text-[10px] font-medium">
                              ✓ Successfully processed
                            </span>
                          )}
                          {staged.status.status === "FAILED" && (
                            <span className="text-red-700 text-[10px] font-medium">
                              ✗ Processing failed
                            </span>
                          )}
                          {staged.status.metadata?.pages && (
                            <span className="text-muted-foreground text-[10px]">
                              {staged.status.metadata.pages} pages
                            </span>
                          )}
                        </div>
                        {staged.status.status !== "COMPLETED" &&
                          staged.status.status !== "FAILED" && (
                            <Progress
                              value={staged.status.progress * 100}
                              className="h-1"
                            />
                          )}
                        {staged.status.metadata && (
                          <div className="flex gap-2 text-[10px] text-muted-foreground">
                            {staged.status.metadata.tables !== undefined && (
                              <span>{staged.status.metadata.tables} tables</span>
                            )}
                            {staged.status.metadata.figures !== undefined && (
                              <span>{staged.status.metadata.figures} figures</span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                    {/* Show backend error message from status polling */}
                    {staged.status?.error_message && (
                      <div className="mt-2 p-2 bg-red-100 border border-red-300 rounded text-[10px] text-red-800">
                        <p className="font-medium mb-1">Processing Error:</p>
                        <p className="whitespace-pre-wrap break-words">{staged.status.error_message}</p>
                      </div>
                    )}
                    {/* Show client-side upload error (fallback) */}
                    {staged.error && !staged.status?.error_message && (
                      <div className="mt-2 p-2 bg-red-100 border border-red-300 rounded text-[10px] text-red-800">
                        <p className="font-medium mb-1">Upload Error:</p>
                        <p className="whitespace-pre-wrap break-words">{staged.error}</p>
                      </div>
                    )}
                  </div>
                  {staged.status?.status === "COMPLETED" && (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 ml-2" />
                  )}
                  {staged.status?.status === "FAILED" && (
                    <AlertCircle className="h-4 w-4 text-destructive shrink-0 ml-2" />
                  )}
                </div>
              ))}
            </div>
            <Button
              onClick={handleStartProcessing}
              disabled={stagedFiles.some((f) => f.ingestion_id)}
              className="w-full border border-slate-900 bg-slate-900 text-white hover:bg-slate-800"
              size="sm"
            >
              Start Processing
            </Button>
          </div>
        )}
      </div>

      {/* Corpus List (Bottom, Flex-grow) */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-shrink-0 p-4 border-b border-slate-200">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search corpus..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {filteredCorpus.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">No files in corpus</p>
            </div>
          ) : (
            <div className="space-y-1">
              {filteredCorpus.map((file, idx) => {
                const statusUpper = file.status?.toUpperCase() || ""
                const isCompleted = statusUpper === "COMPLETED"
                const isFailed = statusUpper === "FAILED"
                const isProcessing = statusUpper && !isCompleted && !isFailed && statusUpper !== "UNKNOWN"
                
                return (
                  <div
                    key={idx}
                    className={`flex items-start justify-between p-2 rounded border text-xs ${
                      isFailed
                        ? "border-red-200 bg-red-50"
                        : isCompleted
                          ? "border-green-200 bg-green-50"
                          : isProcessing
                            ? "border-amber-200 bg-amber-50"
                            : "border-slate-200 bg-white"
                    } hover:opacity-90 transition-colors`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate font-medium">{file.filename}</p>
                        {isCompleted && (
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                        )}
                        {isFailed && (
                          <AlertCircle className="h-3.5 w-3.5 text-red-600 shrink-0" />
                        )}
                        {isProcessing && (
                          <Loader2 className="h-3.5 w-3.5 text-amber-600 shrink-0 animate-spin" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        {isCompleted && file.claims_count !== undefined && (
                          <span className="text-emerald-700 font-medium">
                            ✓ {file.claims_count} claims extracted
                          </span>
                        )}
                        {isFailed && (
                          <span className="text-red-700 font-medium">✗ Processing failed</span>
                        )}
                        {isProcessing && (
                          <span className="text-amber-700">Processing...</span>
                        )}
                        {file.status && (
                          <Badge
                            variant={
                              isCompleted
                                ? "default"
                                : isFailed
                                  ? "destructive"
                                  : "secondary"
                            }
                            className="text-[10px]"
                          >
                            {file.status}
                          </Badge>
                        )}
                      </div>
                      {/* Show error message for failed files */}
                      {isFailed && file.error_message && (
                        <div className="mt-2 p-2 bg-red-100 border border-red-300 rounded text-[10px] text-red-800">
                          <p className="font-medium mb-1">Error:</p>
                          <p className="whitespace-pre-wrap break-words">{file.error_message}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
