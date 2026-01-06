"use client"

/**
 * File Uploader Component for Project Vyasa.
 * Accepts a required projectId prop and uploads files to /ingest/pdf with project association.
 */

import { useState } from "react"
import { Upload, AlertCircle, FileText, Loader2, X, Check, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useProjectFiles } from "@/hooks/use-project-files"

interface UploadResult {
  file: File
  ingestion_id: string
  job_id: string
  status: string
}

interface FileUploaderProps {
  projectId: string
  onUploadComplete?: (result: UploadResult) => void
  onUploadError?: (error: string) => void
  compact?: boolean
}

type FileStatus = "pending" | "uploading" | "success" | "error"

interface QueuedFile {
  file: File
  status: FileStatus
  error?: string
}

export function FileUploader({
  projectId,
  onUploadComplete,
  onUploadError,
  compact = false,
}: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingFiles, setPendingFiles] = useState<QueuedFile[]>([])
  const {
    files: ingestedFiles,
    isLoading: isLoadingFiles,
    error: filesError,
    refresh: refreshFiles,
  } = useProjectFiles(projectId)

  // Safety check: disable if projectId is missing
  if (!projectId) {
    return (
      <Card className="border-destructive/50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-destructive mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-destructive">
                No active project selected.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Please select or create a project to upload files.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  const MAX_FILE_SIZE = 100 * 1024 * 1024 // 100MB in bytes

  const validateFile = (file: File): boolean => {
    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      setError(
        `File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds maximum allowed size (100MB). Please upload a smaller file.`
      )
      return false
    }

    const validTypes = [".pdf", ".md", ".txt", ".json"]
    const isValid = validTypes.some((ext) => file.name.toLowerCase().endsWith(ext))
    if (!isValid) {
      setError(
        `Invalid file type: ${file.name}. Supported: PDF, Markdown, Text, JSON.`
      )
      return false
    }
    return true
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      addPendingFiles(files)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addPendingFiles(Array.from(e.target.files))
      e.target.value = "" // Reset input
    }
  }

  const addPendingFiles = (files: File[]) => {
    const validFiles = files.filter((file) => validateFile(file))
    if (validFiles.length > 0) {
      setPendingFiles((prev) => [
        ...prev,
        ...validFiles.map((file) => ({ file, status: "pending" as FileStatus })),
      ])
      // In compact mode, immediately notify parent of staged files
      // Note: In compact mode, files are staged but not uploaded yet
      // The parent (EvidenceDock) will handle the actual upload
      if (compact) {
        validFiles.forEach((file) => {
          // Pass a placeholder result - actual upload happens in EvidenceDock
          onUploadComplete?.({
            file,
            ingestion_id: "",
            job_id: "",
            status: "pending",
          })
        })
      }
    }
  }

  const removePendingFile = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const formatSize = (size: number) => {
    if (size >= 1024 * 1024) {
      return `${(size / (1024 * 1024)).toFixed(1)} MB`
    }
    if (size >= 1024) {
      return `${(size / 1024).toFixed(1)} KB`
    }
    return `${size} B`
  }

  const processBatch = async () => {
    if (pendingFiles.length === 0) return
    setIsUploading(true)
    setError(null)

    const updatedFiles = [...pendingFiles]

    for (let i = 0; i < updatedFiles.length; i++) {
      const current = updatedFiles[i]
      updatedFiles[i] = { ...current, status: "uploading" }
      setPendingFiles([...updatedFiles])

      try {
        const formData = new FormData()
        formData.append("file", current.file)
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
        // Response: { ingestion_id, job_id, status: "QUEUED" }
        // Status code: 202 Accepted
        const { ingestion_id, job_id, status } = data
        
        if (!ingestion_id) {
          throw new Error("No ingestion_id returned from server")
        }
        
        updatedFiles[i] = { ...current, status: "success" }
        setPendingFiles([...updatedFiles])
        
        // Pass complete upload result with tracking IDs
        onUploadComplete?.({
          file: current.file,
          ingestion_id,
          job_id: job_id || "",
          status: status || "QUEUED",
        })
        refreshFiles()
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed"
        updatedFiles[i] = { ...current, status: "error", error: message }
        setPendingFiles([...updatedFiles])
        setError(message)
        onUploadError?.(message)
      }
    }

    setPendingFiles(updatedFiles)
    setIsUploading(false)
  }

  // Compact mode: just the drop zone, no staging area or corpus list
  if (compact) {
    return (
      <div className="space-y-2">
        {error && (
          <div className="flex items-start gap-2 text-xs text-destructive">
            <AlertCircle className="h-3 w-3 mt-0.5 flex-shrink-0" />
            <p>{error}</p>
          </div>
        )}
        <div
          className={`relative border-2 border-dashed rounded-lg p-3 text-center transition-all duration-200 ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-border/40 hover:border-primary/40"
          } ${isUploading ? "opacity-50 pointer-events-none" : "cursor-pointer"}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isUploading && document.getElementById("file-upload")?.click()}
        >
          <input
            id="file-upload"
            type="file"
            className="hidden"
            accept=".pdf,.md,.txt,.json,application/pdf"
            onChange={handleFileSelect}
            disabled={isUploading}
          />
          <div className="flex flex-col items-center">
            {isUploading ? (
              <Loader2 className="h-5 w-5 text-primary animate-spin mb-2" />
            ) : (
              <Upload className="h-5 w-5 text-primary mb-2" />
            )}
            <p className="text-xs font-medium mb-1">
              {isUploading ? "Uploading..." : "Drop files here"}
            </p>
            <p className="text-[10px] text-muted-foreground">or click to browse</p>
          </div>
        </div>
        {pendingFiles.length > 0 && (
          <div className="text-xs text-muted-foreground">
            {pendingFiles.length} file{pendingFiles.length > 1 ? "s" : ""} staged
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {error && (
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-4 w-4 text-destructive mt-0.5 flex-shrink-0" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <div
        className={`relative border-2 border-dashed rounded-lg p-6 text-center transition-all duration-200 ${
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border/40 hover:border-primary/40"
        } ${isUploading ? "opacity-50 pointer-events-none" : "cursor-pointer"}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && document.getElementById("file-upload")?.click()}
      >
        <input
          id="file-upload"
          type="file"
          className="hidden"
          accept=".pdf,.md,.txt,.json,application/pdf"
          onChange={handleFileSelect}
          disabled={isUploading}
        />
        <div className="flex flex-col items-center">
          {isUploading ? (
            <Loader2 className="h-8 w-8 text-primary animate-spin mb-4" />
          ) : (
            <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4 border border-primary/20">
              <Upload className="h-6 w-6 text-primary" />
            </div>
          )}
          <h3 className="text-sm font-medium mb-1">
            {isUploading ? "Uploading..." : "Drag & Drop File"}
          </h3>
          <p className="text-xs text-muted-foreground mb-3">
            or{" "}
            <Button variant="link" className="h-auto p-0 text-xs" asChild>
              <span>browse files</span>
            </Button>
          </p>
          <div className="inline-flex items-center gap-2 text-xs text-muted-foreground bg-muted/40 px-2 py-1 rounded border border-border/30">
            <FileText className="h-3 w-3" />
            <span>.pdf, .md, .txt, .json</span>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Staging Area</h4>
        {pendingFiles.length === 0 ? (
          <p className="text-xs text-muted-foreground">Drop files to stage them before processing.</p>
        ) : (
          <div className="space-y-2">
            {pendingFiles.map((queued, index) => (
              <div
                key={`${queued.file.name}-${index}`}
                className="flex items-center justify-between rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <div className="flex h-8 w-8 items-center justify-center rounded bg-primary/10 text-primary">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-foreground">{queued.file.name}</p>
                    <p className="text-xs text-muted-foreground">{formatSize(queued.file.size)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {queued.status === "uploading" && (
                    <Loader2 className="h-4 w-4 animate-spin text-primary" title="Uploading" />
                  )}
                  {queued.status === "success" && (
                    <Check className="h-4 w-4 text-emerald-600" title="Uploaded" />
                  )}
                  {queued.status === "error" && (
                    <AlertTriangle
                      className="h-4 w-4 text-destructive"
                      title={queued.error || "Upload failed"}
                    />
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removePendingFile(index)}
                    className="text-muted-foreground hover:text-foreground"
                    disabled={isUploading}
                    aria-label={`Remove ${queued.file.name}`}
                    title={queued.error}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="pt-2">
          <Button
            onClick={processBatch}
            disabled={pendingFiles.length === 0 || isUploading}
            className="border border-slate-900 bg-slate-900 text-white hover:bg-slate-800 hover:border-slate-800 shadow-sm disabled:opacity-50"
          >
            {isUploading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Processing...
              </span>
            ) : (
              "Start Processing"
            )}
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">Ingested Corpus</h4>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={refreshFiles}
            disabled={isLoadingFiles}
          >
            {isLoadingFiles ? (
              <span className="flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                Refreshing
              </span>
            ) : (
              "Refresh"
            )}
          </Button>
        </div>
        {filesError && (
          <p className="text-xs text-destructive">{filesError}</p>
        )}
        {isLoadingFiles ? (
          <p className="text-xs text-muted-foreground">Loading files...</p>
        ) : ingestedFiles.length === 0 ? (
          <p className="text-xs text-muted-foreground">No files in corpus yet.</p>
        ) : (
          <div className="space-y-1">
            {ingestedFiles.map((filename, idx) => (
              <div
                key={`${filename}-${idx}`}
                className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-xs"
              >
                <FileText className="h-4 w-4 text-primary" />
                <span className="truncate">{filename}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
