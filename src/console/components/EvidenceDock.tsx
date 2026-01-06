"use client"

/**
 * Evidence Dock - Left Pane (25% width)
 * Combines compact file uploader, staging area, and corpus list
 */

import { useState, useCallback, useEffect } from "react"
import { FileText, Search, Loader2, CheckCircle2, AlertCircle } from "lucide-react"
import { FileUploader } from "./FileUploader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { useProjectStore } from "@/state/useProjectStore"

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
}

interface StagedFile {
  file: File
  ingestion_id?: string
  job_id?: string
  status?: IngestionStatus
  error?: string
}

interface EvidenceDockProps {
  projectId: string
}

export function EvidenceDock({ projectId }: EvidenceDockProps) {
  const { activeProject } = useProjectStore()
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [corpusFiles, setCorpusFiles] = useState<Array<{ filename: string; claims_count?: number; status?: string }>>([])

  // Poll ingestion status
  const pollIngestionStatus = useCallback(async (ingestionId: string) => {
    try {
      const response = await fetch(
        `/api/proxy/orchestrator/api/projects/${projectId}/ingest/${ingestionId}/status`
      )
      if (!response.ok) return null
      const data = await response.json()
      return {
        ingestion_id: ingestionId,
        status: data.status,
        progress: data.progress || 0,
        metadata: data.metadata,
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
            setStagedFiles((prev) =>
              prev.map((f) =>
                f.ingestion_id === file.ingestion_id ? { ...f, status } : f
              )
            )
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
  }, [stagedFiles, pollIngestionStatus])

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
          `/api/proxy/orchestrator/api/projects/${projectId}/ingest/files`
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
          }))
        )
      }
    }
    
    loadCorpusFiles()
  }, [activeProject, projectId])

  const handleFileStaged = useCallback((result: { file: File; ingestion_id: string; job_id: string; status: string }) => {
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

  const handleStartProcessing = async () => {
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
        const { ingestion_id, job_id, status } = data

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
                }
              : f
          )
        )
      } catch (error) {
        const message = error instanceof Error ? error.message : "Upload failed"
        setStagedFiles((prev) =>
          prev.map((f) => (f.file === staged.file ? { ...f, error: message } : f))
        )
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
        <div className="max-h-[150px] overflow-y-auto">
          <FileUploader
            projectId={projectId}
            onUploadComplete={handleFileStaged}
            compact
          />
        </div>

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
                    <p className="truncate font-medium">{staged.file.name}</p>
                    {staged.status && (
                      <div className="mt-1 space-y-1">
                        <div className="flex items-center gap-2">
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
                          {staged.status.metadata?.pages && (
                            <span className="text-muted-foreground">
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
                    {staged.error && (
                      <p className="text-destructive text-[10px] mt-1">{staged.error}</p>
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
              {filteredCorpus.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 rounded border border-slate-200 bg-white hover:bg-slate-50 text-xs"
                >
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-medium">{file.filename}</p>
                    <div className="flex items-center gap-2 mt-1 text-muted-foreground">
                      {file.claims_count !== undefined && (
                        <span>{file.claims_count} claims</span>
                      )}
                      {file.status && (
                        <Badge variant="outline" className="text-[10px]">
                          {file.status}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

