"use client"

/**
 * File Uploader Component for Project Vyasa.
 * Accepts a required projectId prop and uploads files to /ingest/pdf with project association.
 */

import { useState } from "react"
import { Upload, AlertCircle, FileText, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface FileUploaderProps {
  projectId: string
  onUploadComplete?: (filename: string) => void
  onUploadError?: (error: string) => void
}

export function FileUploader({
  projectId,
  onUploadComplete,
  onUploadError,
}: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

  const handleUpload = async (file: File) => {
    if (!validateFile(file)) {
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("project_id", projectId)

      const response = await fetch("/api/proxy/orchestrator/ingest/pdf", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Upload failed: ${response.statusText}`)
      }

      const data = await response.json()
      onUploadComplete?.(file.name)
      setError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed"
      setError(message)
      onUploadError?.(message)
    } finally {
      setIsUploading(false)
    }
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
      handleUpload(files[0]) // Upload first file only
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleUpload(e.target.files[0])
      e.target.value = "" // Reset input
    }
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
    </div>
  )
}

