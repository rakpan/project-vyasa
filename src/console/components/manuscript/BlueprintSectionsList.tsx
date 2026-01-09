"use client"

/**
 * Blueprint Sections List Component
 * 
 * Displays blueprint sections with status indicators and "Run Section" buttons.
 * Statuses:
 * - Not run yet
 * - Ready (evidence coverage high)
 * - Needs evidence (low retrieval quality)
 * - Has overreach flags (critic)
 * - Visual placeholders pending
 */

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Loader2, Play, CheckCircle2, AlertCircle, Image, FileText } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/hooks/use-toast"

interface BlueprintSection {
  section_id: string
  heading: string
  journal_slot: string
  linked_rqs: string[]
  depth_intent: string
  visual_anchors?: Array<{
    anchor_id: string
    anchor_type: string
    placeholder_text: string
  }>
}

interface SectionStatus {
  section_id: string
  status: "not_run" | "ready" | "needs_evidence" | "has_overreach" | "visual_pending"
  has_blocks: boolean
  block_count: number
  overreach_flags?: number
  visual_anchors_pending?: number
  last_run_job_id?: string
}

interface Ingestion {
  ingestion_id: string
  filename: string
  status: string
  created_at: string
  chunk_count?: number
  triples_count?: number
}

interface BlueprintSectionsListProps {
  projectId: string
  onSectionRun?: (sectionId: string, jobId: string) => void
  onSectionSelect?: (sectionId: string) => void
  selectedSectionId?: string
}

export function BlueprintSectionsList({
  projectId,
  onSectionRun,
  onSectionSelect,
  selectedSectionId,
}: BlueprintSectionsListProps) {
  const [blueprint, setBlueprint] = useState<{ sections: BlueprintSection[] } | null>(null)
  const [sectionStatuses, setSectionStatuses] = useState<Map<string, SectionStatus>>(new Map())
  const [runningSections, setRunningSections] = useState<Set<string>>(new Set())
  const [sectionStages, setSectionStages] = useState<Map<string, string | null>>(new Map()) // Track current stage for running sections
  const [isLoading, setIsLoading] = useState(true)
  const [ingestions, setIngestions] = useState<Ingestion[]>([])
  const [selectedIngestionId, setSelectedIngestionId] = useState<string>("")
  const [isLoadingIngestions, setIsLoadingIngestions] = useState(true)

  // Fetch blueprint
  useEffect(() => {
    const fetchBlueprint = async () => {
      try {
        const response = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/blueprint`)
        if (response.ok) {
          const data = await response.json()
          setBlueprint(data)
        } else if (response.status !== 404) {
          throw new Error(`Failed to fetch blueprint: ${response.status}`)
        }
      } catch (error) {
        console.error("Failed to fetch blueprint:", error)
        toast({
          title: "Error",
          description: "Failed to load blueprint",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
      }
    }

    if (projectId) {
      fetchBlueprint()
    }
  }, [projectId])

  // Fetch completed ingestions
  useEffect(() => {
    const fetchIngestions = async () => {
      setIsLoadingIngestions(true)
      try {
        const response = await fetch(
          `/api/proxy/orchestrator/api/projects/${projectId}/ingestions?status=COMPLETED`
        )
        if (response.ok) {
          const data = await response.json()
          const completedIngestions = data.ingestions || []
          setIngestions(completedIngestions)
          
          // Default to most recent completed ingestion
          if (completedIngestions.length > 0 && !selectedIngestionId) {
            setSelectedIngestionId(completedIngestions[0].ingestion_id)
          }
        } else if (response.status !== 404) {
          throw new Error(`Failed to fetch ingestions: ${response.status}`)
        }
      } catch (error) {
        console.error("Failed to fetch ingestions:", error)
        toast({
          title: "Warning",
          description: "Failed to load ingestions. Section runs may fail without ingestion_id.",
          variant: "destructive",
        })
      } finally {
        setIsLoadingIngestions(false)
      }
    }

    if (projectId) {
      fetchIngestions()
    }
  }, [projectId, selectedIngestionId])

  // Fetch section statuses (check for blocks and critique flags)
  useEffect(() => {
    const fetchSectionStatuses = async () => {
      if (!blueprint || !blueprint.sections) return

      const statusMap = new Map<string, SectionStatus>()

      for (const section of blueprint.sections) {
        try {
          // Check if section has blocks
          const blocksResponse = await fetch(
            `/api/proxy/orchestrator/api/projects/${projectId}/manuscript/blocks?section_id=${section.section_id}`
          )
          const blocks = blocksResponse.ok ? await blocksResponse.json() : []

          // Determine status
          let status: SectionStatus["status"] = "not_run"
          let overreachFlags = 0
          let visualAnchorsPending = 0

          if (blocks.length > 0) {
            // Section has been run - check for issues
            // TODO: Check for overreach flags from critique (stored in block metadata or separate endpoint)
            // For now, assume ready if blocks exist
            status = "ready"

            // Check for visual anchors pending
            if (section.visual_anchors && section.visual_anchors.length > 0) {
              visualAnchorsPending = section.visual_anchors.length
              // TODO: Check if anchors have been filled
              // For now, mark as pending if anchors exist
              if (visualAnchorsPending > 0) {
                status = "visual_pending"
              }
            }
          }

          statusMap.set(section.section_id, {
            section_id: section.section_id,
            status,
            has_blocks: blocks.length > 0,
            block_count: blocks.length,
            overreach_flags: overreachFlags,
            visual_anchors_pending: visualAnchorsPending,
          })
        } catch (error) {
          console.error(`Failed to fetch status for section ${section.section_id}:`, error)
          statusMap.set(section.section_id, {
            section_id: section.section_id,
            status: "not_run",
            has_blocks: false,
            block_count: 0,
          })
        }
      }

      setSectionStatuses(statusMap)
    }

    fetchSectionStatuses()
  }, [blueprint, projectId])

  // Handle run section with polling
  const handleRunSection = async (sectionId: string) => {
    if (!selectedIngestionId) {
      toast({
        title: "Error",
        description: "Please select an ingestion before running the section",
        variant: "destructive",
      })
      return
    }

    // Prevent duplicate runs
    if (runningSections.has(sectionId)) {
      return
    }

    setRunningSections((prev) => new Set(prev).add(sectionId))

    try {
      const response = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/sections/${sectionId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ingestion_id: selectedIngestionId,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const errorMessage = errorData.error || `Failed to run section: ${response.status}`
        throw new Error(errorMessage)
      }

      const data = await response.json()
      const jobId = data.job_id || data.results?.job_id

      if (!jobId) {
        throw new Error("No job_id returned from section run")
      }

      toast({
        title: "Success",
        description: "Section synthesis started",
      })

      if (onSectionRun) {
        onSectionRun(sectionId, jobId)
      }

      // Poll for status with exponential backoff
      // Delays: 1s → 2s → 4s → 8s (capped), then 8s for remaining polls
      // Worst-case duration: ~40 minutes (1+2+4+8 + 296*8 = 2383s)
      let pollDelay = 1000 // Start with 1 second
      const maxDelay = 8000 // Cap at 8 seconds
      const maxDurationMs = 10 * 60 * 1000 // Safety cap: 10 minutes (600,000ms)
      const startTime = Date.now()
      let pollCount = 0
      const maxPolls = 300 // Max polls (worst-case ~40 minutes with exponential backoff)

      const pollStatus = async (): Promise<void> => {
        if (!runningSections.has(sectionId)) {
          // Section run was cancelled
          return
        }

        try {
          const statusResponse = await fetch(
            `/api/proxy/orchestrator/api/projects/${projectId}/sections/${sectionId}/status?job_id=${jobId}`
          )

          if (!statusResponse.ok) {
            if (statusResponse.status === 404) {
              // Job not found yet, continue polling
              // Check duration cap first (safety net)
              const elapsedMs = Date.now() - startTime
              if (elapsedMs >= maxDurationMs) {
                throw new Error("Section synthesis timed out after 10 minutes")
              }
              
              pollCount++
              if (pollCount < maxPolls) {
                setTimeout(pollStatus, pollDelay)
                pollDelay = Math.min(pollDelay * 2, maxDelay) // Exponential backoff with cap
              } else {
                throw new Error("Section synthesis timed out after maximum polling attempts (~40 minutes)")
              }
              return
            }
            throw new Error(`Failed to get status: ${statusResponse.status}`)
          }

          const statusData = await statusResponse.json()
          const status = statusData.status
          const stage = statusData.stage
          const progressPercent = statusData.progress_percent || 0
          const error = statusData.error
          const result = statusData.result

          // Update stage tracking for UI display (null-safe)
          setSectionStages((prev) => {
            const updated = new Map(prev)
            updated.set(sectionId, stage) // stage can be null, which is fine
            return updated
          })

          // Update UI with progress
          if (stage) {
            const stageMessages: Record<string, string> = {
              query: "Building query",
              retrieval: "Retrieving evidence",
              rerank: "Reranking results",
              packet_a: "Building evidence packet",
              packet_b: "Building notes packet",
              synthesis: "Synthesizing content",
              critique: "Validating content",
              persist: "Saving blocks",
              complete: "Completing",
            }
            const message = stageMessages[stage] || stage
            // Could show progress toast here if desired
          }
          // If stage is null, we're in an unknown/unmapped state - still show progress if available

          if (status === "SUCCEEDED" || status === "COMPLETED") {
            // Success - refresh section status
            const blocksResponse = await fetch(
              `/api/proxy/orchestrator/api/projects/${projectId}/manuscript/blocks?section_id=${sectionId}`
            )
            if (blocksResponse.ok) {
              const blocks = await blocksResponse.json()
              setSectionStatuses((prev) => {
                const updated = new Map(prev)
                const current = updated.get(sectionId) || {
                  section_id: sectionId,
                  status: "not_run" as const,
                  has_blocks: false,
                  block_count: 0,
                }
                updated.set(sectionId, {
                  ...current,
                  status: blocks.length > 0 ? "ready" : "not_run",
                  has_blocks: blocks.length > 0,
                  block_count: blocks.length,
                  last_run_job_id: jobId,
                })
                return updated
              })
            }

            toast({
              title: "Success",
              description: `Section synthesis completed${result?.block_id ? ` (block: ${result.block_id.substring(0, 8)}...)` : ""}`,
            })

            // Stop polling
            setRunningSections((prev) => {
              const updated = new Set(prev)
              updated.delete(sectionId)
              return updated
            })
            setSectionStages((prev) => {
              const updated = new Map(prev)
              updated.delete(sectionId)
              return updated
            })
            return
          } else if (status === "FAILED" || status === "ERROR") {
            // Failure
            const errorMessage = error || "Section synthesis failed"
            toast({
              title: "Error",
              description: errorMessage,
              variant: "destructive",
            })

            // Stop polling
            setRunningSections((prev) => {
              const updated = new Set(prev)
              updated.delete(sectionId)
              return updated
            })
            setSectionStages((prev) => {
              const updated = new Map(prev)
              updated.delete(sectionId)
              return updated
            })
            return
          } else {
            // Still running - continue polling
            // Check duration cap first (safety net)
            const elapsedMs = Date.now() - startTime
            if (elapsedMs >= maxDurationMs) {
              throw new Error("Section synthesis timed out after 10 minutes")
            }
            
            pollCount++
            if (pollCount < maxPolls) {
              setTimeout(pollStatus, pollDelay)
              pollDelay = Math.min(pollDelay * 2, maxDelay) // Exponential backoff with cap
            } else {
              throw new Error("Section synthesis timed out after maximum polling attempts (~40 minutes)")
            }
          }
        } catch (error) {
          console.error("Failed to poll section status:", error)
          toast({
            title: "Error",
            description: error instanceof Error ? error.message : "Failed to poll section status",
            variant: "destructive",
          })
          setRunningSections((prev) => {
            const updated = new Set(prev)
            updated.delete(sectionId)
            return updated
          })
          setSectionStages((prev) => {
            const updated = new Map(prev)
            updated.delete(sectionId)
            return updated
          })
        }
      }

      // Start polling after initial delay
      setTimeout(pollStatus, pollDelay)
    } catch (error) {
      console.error("Failed to run section:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to run section",
        variant: "destructive",
      })
      setRunningSections((prev) => {
        const updated = new Set(prev)
        updated.delete(sectionId)
        return updated
      })
    }
  }

  const getStatusBadge = (status: SectionStatus["status"]) => {
    switch (status) {
      case "not_run":
        return <Badge variant="outline" className="text-xs">Not Run</Badge>
      case "ready":
        return (
          <Badge variant="default" className="text-xs bg-green-600">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            Ready
          </Badge>
        )
      case "needs_evidence":
        return (
          <Badge variant="destructive" className="text-xs">
            <AlertCircle className="h-3 w-3 mr-1" />
            Needs Evidence
          </Badge>
        )
      case "has_overreach":
        return (
          <Badge variant="destructive" className="text-xs">
            <AlertCircle className="h-3 w-3 mr-1" />
            Overreach Flags
          </Badge>
        )
      case "visual_pending":
        return (
          <Badge variant="secondary" className="text-xs">
            <Image className="h-3 w-3 mr-1" />
            Visual Pending
          </Badge>
        )
      default:
        return <Badge variant="outline" className="text-xs">Unknown</Badge>
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!blueprint || !blueprint.sections || blueprint.sections.length === 0) {
    return (
      <div className="p-4 text-center text-sm text-muted-foreground">
        No blueprint found. Create one in the Perspectives page.
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <CardHeader className="border-b">
        <CardTitle className="text-sm">Blueprint Sections</CardTitle>
      </CardHeader>
      <div className="p-4 border-b">
        <div className="space-y-2">
          <Label htmlFor="ingestion-select" className="text-xs font-semibold">
            Ingestion (for retrieval)
          </Label>
          <Select
            value={selectedIngestionId}
            onValueChange={setSelectedIngestionId}
            disabled={isLoadingIngestions || ingestions.length === 0}
          >
            <SelectTrigger id="ingestion-select" className="h-8 text-xs">
              <SelectValue placeholder={isLoadingIngestions ? "Loading..." : ingestions.length === 0 ? "No completed ingestions" : "Select ingestion"} />
            </SelectTrigger>
            <SelectContent>
              {ingestions.map((ingestion) => (
                <SelectItem key={ingestion.ingestion_id} value={ingestion.ingestion_id}>
                  <div className="flex flex-col">
                    <span className="text-xs font-medium">{ingestion.filename}</span>
                    <span className="text-[10px] text-muted-foreground">
                      {ingestion.chunk_count !== undefined ? `${ingestion.chunk_count} chunks` : ""}
                      {ingestion.chunk_count !== undefined && ingestion.triples_count !== undefined ? " • " : ""}
                      {ingestion.triples_count !== undefined ? `${ingestion.triples_count} triples` : ""}
                      {ingestion.created_at ? ` • ${new Date(ingestion.created_at).toLocaleDateString()}` : ""}
                    </span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {ingestions.length === 0 && !isLoadingIngestions && (
            <p className="text-xs text-muted-foreground">
              No completed ingestions found. Upload and process documents first.
            </p>
          )}
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3">
          {blueprint.sections.map((section) => {
            const status = sectionStatuses.get(section.section_id) || {
              section_id: section.section_id,
              status: "not_run" as const,
              has_blocks: false,
              block_count: 0,
            }
            const isRunning = runningSections.has(section.section_id)
            const isSelected = selectedSectionId === section.section_id

            return (
              <Card
                key={section.section_id}
                className={cn(
                  "cursor-pointer transition-colors hover:bg-accent",
                  isSelected && "ring-2 ring-primary"
                )}
                onClick={() => onSectionSelect?.(section.section_id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold mb-1">{section.heading}</h4>
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline" className="text-[10px]">
                          {section.journal_slot}
                        </Badge>
                        {getStatusBadge(status.status)}
                        {status.block_count > 0 && (
                          <span className="text-xs text-muted-foreground">
                            {status.block_count} block{status.block_count !== 1 ? "s" : ""}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {section.linked_rqs && section.linked_rqs.length > 0 && (
                    <div className="text-xs text-muted-foreground mb-2">
                      RQs: {section.linked_rqs.join(", ")}
                    </div>
                  )}

                  {status.visual_anchors_pending && status.visual_anchors_pending > 0 && (
                    <div className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                      <Image className="h-3 w-3" />
                      {status.visual_anchors_pending} visual placeholder{status.visual_anchors_pending !== 1 ? "s" : ""} pending
                    </div>
                  )}

                  <div className="flex flex-col items-end mt-3 gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleRunSection(section.section_id)
                      }}
                      disabled={isRunning}
                      className="h-7 text-xs"
                    >
                      {isRunning ? (
                        <>
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          Running...
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3 mr-1" />
                          Run Section
                        </>
                      )}
                    </Button>
                    {isRunning && (() => {
                      const currentStage = sectionStages.get(section.section_id)
                      if (currentStage) {
                        const stageLabels: Record<string, string> = {
                          query: "Building query",
                          retrieval: "Retrieving evidence",
                          rerank: "Reranking results",
                          packet_a: "Building evidence packet",
                          packet_b: "Building notes packet",
                          synthesis: "Synthesizing content",
                          critique: "Validating content",
                          persist: "Saving blocks",
                          complete: "Completing",
                        }
                        const stageLabel = stageLabels[currentStage] || currentStage
                        return (
                          <span className="text-[10px] text-muted-foreground">
                            {stageLabel}
                          </span>
                        )
                      }
                      return null
                    })()}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </ScrollArea>
    </div>
  )
}
