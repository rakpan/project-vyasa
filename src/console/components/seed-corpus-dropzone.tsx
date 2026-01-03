"use client"

/**
 * Seed Corpus Dropzone Component
 * Drag/drop zone for PDF files with hover highlight
 * Spans left+center panes at top of workbench
 */

import { useState, useRef, useCallback } from "react"
import { Upload, FileText, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

interface SeedCorpusDropzoneProps {
  onFileSelect: (file: File) => void
  disabled?: boolean
  className?: string
}

export function SeedCorpusDropzone({
  onFileSelect,
  disabled = false,
  className,
}: SeedCorpusDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) {
      setIsDragOver(true)
    }
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)

    if (disabled) return

    const files = Array.from(e.dataTransfer.files)
    const pdfFile = files.find((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"))

    if (pdfFile) {
      onFileSelect(pdfFile)
    }
  }, [disabled, onFileSelect])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const file = files[0]
      if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
        onFileSelect(file)
      }
    }
    // Reset input to allow selecting the same file again
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }, [onFileSelect])

  const handleClick = useCallback(() => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click()
    }
  }, [disabled])

  return (
    <div
      className={cn(
        "relative border-2 border-dashed rounded-lg transition-all duration-200",
        isDragOver
          ? "border-primary bg-primary/5 scale-[1.02]"
          : "border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label="Drop PDF files here or click to select"
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) {
          e.preventDefault()
          handleClick()
        }
      }}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleFileInput}
        className="hidden"
        disabled={disabled}
        aria-label="Select PDF file"
      />

      <div className="flex flex-col items-center justify-center p-8 text-center">
        <div className={cn(
          "mb-4 p-4 rounded-full bg-background border-2 transition-colors",
          isDragOver ? "border-primary" : "border-border"
        )}>
          {isDragOver ? (
            <Upload className="h-8 w-8 text-primary animate-bounce" />
          ) : (
            <FileText className="h-8 w-8 text-muted-foreground" />
          )}
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">
            {isDragOver ? "Drop PDF here" : "Drop PDF files here or click to select"}
          </p>
          <p className="text-xs text-muted-foreground">
            Only PDF files are supported
          </p>
        </div>

        {!isDragOver && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-4"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation()
              handleClick()
            }}
          >
            <Upload className="h-4 w-4 mr-2" />
            Select PDF
          </Button>
        )}
      </div>
    </div>
  )
}

