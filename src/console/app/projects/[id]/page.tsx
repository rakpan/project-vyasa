"use client"

/**
 * Project Workbench Page - 3-column dashboard for project work.
 * Left: Seed Corpus (file list + uploader)
 * Center: Processing (extraction results / graph view)
 * Right: Intent Context (thesis, RQs, anti-scope)
 */

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { FileText, Target, BookOpen, Play, Loader2, ExternalLink, Clock } from "lucide-react"
import { useProjectStore } from "@/state/useProjectStore"
import { FileUploader } from "@/components/FileUploader"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { toast } from "@/hooks/use-toast"

export default function ProjectWorkbenchPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string
  const {
    activeProjectId,
    activeProject,
    isLoading,
    error,
    setActiveProject,
  } = useProjectStore()
  const [isStarting, setIsStarting] = useState(false)
  const [recentJobs, setRecentJobs] = useState<any[]>([])
  const [loadingJobs, setLoadingJobs] = useState(false)

  // Fetch recent jobs for this project
  useEffect(() => {
    if (!projectId) return
    setLoadingJobs(true)
    const fetchJobs = async () => {
      try {
        const response = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/jobs?limit=5`)
        if (response.ok) {
          const data = await response.json()
          setRecentJobs(data.jobs || [])
        }
      } catch (err) {
        console.error("Failed to fetch jobs:", err)
        setRecentJobs([])
      } finally {
        setLoadingJobs(false)
      }
    }
    fetchJobs()
  }, [projectId])

  const handleOpenWorkbench = (job: any) => {
    const pdfRaw = job.pdf_url || job.pdfUrl || job.pdf_path
    const pdfUrl = pdfRaw
      ? `/api/proxy/orchestrator/files/${encodeURIComponent(pdfRaw)}`
      : ""
    const params = new URLSearchParams({
      jobId: job.job_id,
      projectId: projectId,
    })
    if (pdfUrl) {
      params.set("pdfUrl", pdfUrl)
    }
    router.push(`/research-workbench?${params.toString()}`)
  }

  const getStatusBadgeVariant = (status: string) => {
    const statusLower = (status || "").toLowerCase()
    if (["succeeded", "completed", "finalized"].includes(statusLower)) {
      return "default"
    }
    if (["failed", "error"].includes(statusLower)) {
      return "destructive"
    }
    if (["queued", "running", "processing"].includes(statusLower)) {
      return "secondary"
    }
    return "outline"
  }

  // Ensure active project matches route param
  useEffect(() => {
    if (projectId && activeProjectId !== projectId) {
      setActiveProject(projectId)
    }
  }, [projectId, activeProjectId, setActiveProject])

  // Refresh project after upload to get updated seed_files
  const handleUploadComplete = () => {
    if (projectId) {
      setActiveProject(projectId)
    }
  }

  // Start Research: Submit a job and navigate to workbench
  const handleStartResearch = async () => {
    if (!activeProject) {
      toast({
        title: "Project not loaded",
        description: "Please wait for the project to load.",
        variant: "destructive",
      })
      return
    }

    // Find first PDF file
    const pdfFiles = activeProject.seed_files.filter((f) => 
      f.toLowerCase().endsWith(".pdf")
    )
    
    if (pdfFiles.length === 0) {
      toast({
        title: "No PDF files",
        description: "Please upload a PDF file before starting research.",
        variant: "destructive",
      })
      return
    }

    const selectedFile = pdfFiles[0]
    setIsStarting(true)

    try {
      // Construct file URL for PDF viewer (will be passed in navigation)
      // In production, this would point to an actual file serving endpoint
      const fileUrl = `/api/proxy/orchestrator/files/${encodeURIComponent(selectedFile)}`
      
      // Submit job via workflow/submit endpoint with JSON payload
      // The server will need to handle the pdf_path and extract text
      // Note: This assumes the file is already processed/stored server-side
      // For files that need to be uploaded, you'd use multipart/form-data instead
      const response = await fetch("/api/proxy/orchestrator/workflow/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          pdf_path: selectedFile,
          raw_text: "", // Will be extracted from PDF on server if pdf_path is provided
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Job submission failed: ${response.statusText}`)
      }

      const result = await response.json()
      const jobId = result.job_id

      // Navigate to workbench with all required params
      router.push(
        `/research-workbench?jobId=${jobId}&projectId=${projectId}&pdfUrl=${encodeURIComponent(fileUrl)}`
      )

      toast({
        title: "Research started",
        description: `Job ${jobId.substring(0, 8)}... has been queued.`,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start research"
      toast({
        title: "Start failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setIsStarting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-6">
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">Loading project...</p>
        </div>
      </div>
    )
  }

  if (error || !activeProject) {
    return (
      <div className="container mx-auto px-4 py-6">
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">
              {error || "Project not found"}
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-6 max-w-[1600px]">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold mb-1">{activeProject.title}</h1>
        <p className="text-sm text-muted-foreground">
          Created {new Date(activeProject.created_at).toLocaleDateString()}
        </p>
      </div>

      {/* 3-Column Grid Layout */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column: Seed Corpus (25%) */}
        <div className="col-span-12 md:col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Seed Corpus
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Uploader */}
              <FileUploader
                projectId={projectId}
                onUploadComplete={handleUploadComplete}
                onUploadError={(error) => {
                  console.error(`Upload error: ${error}`)
                }}
              />

              {/* File List */}
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Files ({activeProject.seed_files.length})
                </p>
                {activeProject.seed_files.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No files uploaded yet
                  </p>
                ) : (
                  <div className="space-y-1">
                    {activeProject.seed_files.map((filename, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between text-xs p-2 rounded border border-border/30 bg-muted/20 hover:bg-muted/40"
                      >
                        <span className="truncate flex-1">{filename}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Start Research Button */}
                {activeProject.seed_files.length > 0 && (
                  <Button
                    onClick={handleStartResearch}
                    disabled={isStarting}
                    className="w-full mt-4"
                    size="sm"
                  >
                    {isStarting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Starting...
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-4 w-4" />
                        Start Research
                      </>
                    )}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Center Column: Recent Jobs (50%) */}
        <div className="col-span-12 md:col-span-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Target className="h-4 w-4" />
                Recent Jobs
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loadingJobs ? (
                <div className="py-8 text-center">
                  <Loader2 className="h-4 w-4 animate-spin mx-auto mb-2 text-muted-foreground" />
                  <p className="text-xs text-muted-foreground">Loading jobs...</p>
                </div>
              ) : recentJobs.length === 0 ? (
                <div className="py-12 text-center space-y-3">
                  <p className="text-sm text-muted-foreground">No jobs yet</p>
                  {activeProject.seed_files.length > 0 && (
                    <Button
                      onClick={handleStartResearch}
                      disabled={isStarting}
                      size="sm"
                      variant="outline"
                    >
                      <Play className="mr-2 h-3 w-3" />
                      Start Research
                    </Button>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  {recentJobs.map((job) => (
                    <div
                      key={job.job_id}
                      className="flex items-center justify-between p-3 rounded-lg border border-border/30 bg-muted/20 hover:bg-muted/40 transition-colors"
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <Badge variant={getStatusBadgeVariant(job.status)} className="text-xs shrink-0">
                          {job.status}
                        </Badge>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Clock className="h-3 w-3 shrink-0" />
                            <span className="truncate">
                              {job.created_at
                                ? new Date(job.created_at).toLocaleDateString("en-US", {
                                    month: "short",
                                    day: "numeric",
                                    year: "numeric",
                                  })
                                : "Unknown date"}
                            </span>
                            {job.job_version && job.job_version > 1 && (
                              <Badge variant="outline" className="text-[10px] px-1 py-0">
                                v{job.job_version}
                              </Badge>
                            )}
                          </div>
                          <div className="text-[10px] font-mono text-muted-foreground mt-0.5 truncate">
                            {job.job_id.substring(0, 8)}...
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenWorkbench(job)}
                        className="h-7 text-xs shrink-0"
                      >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        Open
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Intent Context (25%) */}
        <div className="col-span-12 md:col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BookOpen className="h-4 w-4" />
                Intent Context
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Thesis */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Thesis
                </p>
                <p className="text-sm leading-relaxed">{activeProject.thesis}</p>
              </div>

              {/* Research Questions */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Research Questions
                </p>
                <ul className="space-y-2">
                  {activeProject.research_questions.map((rq, idx) => (
                    <li key={idx} className="text-sm flex items-start gap-2">
                      <span className="text-muted-foreground mt-1">•</span>
                      <span className="flex-1">{rq}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Anti-Scope */}
              {activeProject.anti_scope && activeProject.anti_scope.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Anti-Scope
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {activeProject.anti_scope.map((item, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Target Journal */}
              {activeProject.target_journal && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Target Journal
                  </p>
                  <Badge variant="secondary" className="text-xs">
                    {activeProject.target_journal}
                  </Badge>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
