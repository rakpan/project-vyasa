"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Loader2, X, CheckCircle2, AlertCircle, ExternalLink } from "lucide-react"
import { toast } from "@/hooks/use-toast"
import { createAbortableFetch, createIsMountedRef, startPolling } from "@/lib/async"

interface ResearchSideloaderProps {
  projectId?: string
  onIngested?: (referenceId: string) => void
}

export function ResearchSideloader({ projectId, onIngested }: ResearchSideloaderProps) {
  const [contentRaw, setContentRaw] = useState("")
  const [sourceName, setSourceName] = useState("Perplexity")
  const [sourceUrl, setSourceUrl] = useState("")
  const [tags, setTags] = useState<string[]>(["OOB"])
  const [tagInput, setTagInput] = useState("")
  const [projectIdInput, setProjectIdInput] = useState(projectId || "")
  const [ingesting, setIngesting] = useState(false)
  const [referenceId, setReferenceId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  useEffect(() => {
    if (projectId) {
      setProjectIdInput(projectId)
    }
  }, [projectId])

  useEffect(() => {
    // Only start polling if we have a referenceId
    if (!referenceId) return

    // Track component mount status to prevent setState after unmount
    const mountedRef = createIsMountedRef()

    // Terminal statuses that should stop polling
    const terminalStatuses = ["EXTRACTED", "NEEDS_REVIEW", "PROMOTED", "REJECTED"]

    // Start polling with proper cleanup
    const pollingController = startPolling({
      intervalMs: 2000,
      immediate: true,
      fn: async (signal) => {
        try {
          // Use abortable fetch to ensure cancellation on unmount
          const { promise } = createAbortableFetch<{
            reference?: { status?: string }
          }>(
            `/api/proxy/orchestrator/api/knowledge/references/${referenceId}`,
            { signal }
          )

          const data = await promise
          const currentStatus = data.reference?.status

          // Only update state if component is still mounted
          if (mountedRef.isMounted() && currentStatus) {
            setStatus(currentStatus)

            // Stop polling when status reaches terminal state
            if (terminalStatuses.includes(currentStatus)) {
              pollingController.stop("Status reached terminal state")

              // Show appropriate toast based on terminal status
              if (currentStatus === "EXTRACTED") {
                toast({
                  title: "Extraction complete",
                  description: "Facts have been extracted and are ready for review.",
                })
              } else if (currentStatus === "NEEDS_REVIEW") {
                toast({
                  title: "Review required",
                  description: "Extraction completed but requires review.",
                  variant: "default",
                })
              } else if (currentStatus === "REJECTED") {
                toast({
                  title: "Reference Rejected",
                  description: "The reference was rejected and will not be used.",
                  variant: "destructive",
                })
              }
            }
          }
        } catch (err) {
          // Ignore AbortError (expected when stopping)
          if (err instanceof Error && err.name === "AbortError") {
            return
          }

          // Only log errors if component is still mounted
          if (mountedRef.isMounted()) {
            console.error("Failed to poll reference status:", err)
          }
        }
      },
      onError: (error) => {
        // Error handler only called for non-abort errors
        if (mountedRef.isMounted() && error.name !== "AbortError") {
          console.error("Polling error:", error)
        }
      },
    })

    // Cleanup: mark as unmounted and stop polling
    return () => {
      mountedRef.unmount()
      pollingController.stop("Component unmounted")
    }
  }, [referenceId]) // Only depend on referenceId, not status

  const handleAddTag = () => {
    const trimmed = tagInput.trim()
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed])
      setTagInput("")
    }
  }

  const handleRemoveTag = (tagToRemove: string) => {
    if (tagToRemove === "OOB") return // Prevent removing OOB tag
    setTags(tags.filter(tag => tag !== tagToRemove))
  }

  const handleTagInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault()
      handleAddTag()
    }
  }

  const handleSubmit = async () => {
    if (!contentRaw.trim()) {
      toast({
        title: "Content required",
        description: "Please paste or enter content to ingest.",
        variant: "destructive",
      })
      return
    }

    // Validate projectId is present and not empty
    if (!projectIdInput || !projectIdInput.trim()) {
      toast({
        title: "Project required",
        description: "Please select a project before sideloading research.",
        variant: "destructive",
      })
      return
    }

    setIngesting(true)
    setReferenceId(null)
    setStatus(null)

    try {
      const response = await fetch("/api/proxy/orchestrator/api/knowledge/sideload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectIdInput.trim(),
          content_raw: contentRaw.trim(),
          source_name: sourceName.trim() || "Perplexity",
          source_url: sourceUrl.trim() || undefined,
          source_type: "human_oracle",
          tags: tags,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Ingestion failed: ${response.statusText}`)
      }

      const result = await response.json()
      setReferenceId(result.reference_id)
      setStatus(result.status)

      toast({
        title: "Ingestion started",
        description: `Reference ${result.reference_id.substring(0, 8)}... is being processed.`,
      })

      onIngested?.(result.reference_id)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to ingest knowledge"
      toast({
        title: "Ingestion failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setIngesting(false)
    }
  }

  const getStatusBadge = (currentStatus: string | null) => {
    if (!currentStatus) return null

    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      INGESTED: "default",
      EXTRACTING: "secondary",
      EXTRACTED: "outline",
      NEEDS_REVIEW: "secondary",
      PROMOTED: "outline",
      REJECTED: "destructive",
    }

    return (
      <Badge variant={variants[currentStatus] || "default"} className="flex items-center gap-2">
        {currentStatus === "EXTRACTED" && <CheckCircle2 className="h-3 w-3" />}
        {currentStatus === "EXTRACTING" && <Loader2 className="h-3 w-3 animate-spin" />}
        {currentStatus}
      </Badge>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Research Sideloader</CardTitle>
        <CardDescription>
          Paste external research content (Perplexity, web articles, etc.) to ingest into Vyasa
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Project ID */}
        <div className="space-y-2">
          <Label htmlFor="project_id">Project ID *</Label>
          <Input
            id="project_id"
            value={projectIdInput}
            onChange={(e) => setProjectIdInput(e.target.value)}
            placeholder="project-uuid"
            disabled={!!projectId || ingesting}
          />
        </div>

        {/* Source Name */}
        <div className="space-y-2">
          <Label htmlFor="source_name">Source Name</Label>
          <Input
            id="source_name"
            value={sourceName}
            onChange={(e) => setSourceName(e.target.value)}
            placeholder="Perplexity"
            disabled={ingesting}
          />
        </div>

        {/* Source URL */}
        <div className="space-y-2">
          <Label htmlFor="source_url">Source URL (optional)</Label>
          <Input
            id="source_url"
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://..."
            disabled={ingesting}
          />
        </div>

        {/* Tags */}
        <div className="space-y-2">
          <Label>Tags</Label>
          <div className="flex flex-wrap gap-2 mb-2">
            {tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="flex items-center gap-1">
                {tag}
                {tag !== "OOB" && (
                  <button
                    onClick={() => handleRemoveTag(tag)}
                    className="ml-1 hover:text-destructive"
                    disabled={ingesting}
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </Badge>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={handleTagInputKeyDown}
              placeholder="Add tag..."
              disabled={ingesting}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddTag}
              disabled={ingesting || !tagInput.trim()}
            >
              Add
            </Button>
          </div>
        </div>

        {/* Content Textarea */}
        <div className="space-y-2">
          <Label htmlFor="content">Content *</Label>
          <Textarea
            id="content"
            value={contentRaw}
            onChange={(e) => setContentRaw(e.target.value)}
            placeholder="Paste research content here..."
            className="min-h-[200px] font-mono text-sm"
            disabled={ingesting}
          />
          <p className="text-xs text-muted-foreground">
            {contentRaw.length} characters
          </p>
        </div>

        {/* Status Display */}
        {referenceId && status && (
          <div className="p-3 rounded-md bg-muted flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Reference ID:</span>
              <code className="text-xs bg-background px-2 py-1 rounded">
                {referenceId.substring(0, 8)}...
              </code>
            </div>
            {getStatusBadge(status)}
          </div>
        )}

        {/* Submit Button */}
        <Button
          onClick={handleSubmit}
          disabled={ingesting || !contentRaw.trim() || !projectIdInput.trim()}
          className="w-full"
        >
          {ingesting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Ingesting...
            </>
          ) : (
            "Ingest Knowledge"
          )}
        </Button>

        {referenceId && (
          <div className="pt-2">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => window.open(`/knowledge/references/${referenceId}`, "_blank")}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Review Reference
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
