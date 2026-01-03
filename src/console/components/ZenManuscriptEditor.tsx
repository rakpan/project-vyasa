"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Plus, Trash2, BookOpen, FileEdit, X, CheckCircle2, XCircle, MessageSquare, GitBranch } from "lucide-react"
import { useResearchStore } from "@/state/useResearchStore"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { ClaimIdLink } from "./claim-id-link"
import { ForkDialog } from "./fork-dialog"
import { toast } from "@/hooks/use-toast"

type Block = {
  id: string
  section_title: string
  content: string
  citation_keys: string[]
  claim_ids: string[]
  confidence?: number
  created_at?: string
  status?: "pending" | "accepted" | "rejected"
  notes?: string
  block_id?: string // For API calls
  rigor_level?: string // Current rigor level
}

type ForkedBlock = {
  block_id: string
  section_title: string
  content: string
  claim_ids: string[]
  citation_keys: string[]
  rigor_level: string
  original_version: number
}

type ZenManuscriptEditorProps = {
  projectId?: string
  blocks?: Block[]
  jobId?: string // For fetching claim data
}

/**
 * Zen-First Manuscript Editor with Ghost Mode and Collapsible Sidebars.
 * - Add/Delete buttons only appear on active block
 * - Librarian (Citation) and Patch (AI Suggestions) sidebars are collapsible
 */
export function ZenManuscriptEditor({ projectId, blocks = [], jobId }: ZenManuscriptEditorProps) {
  const [localBlocks, setLocalBlocks] = useState<Block[]>(blocks)
  const [claimDataMap, setClaimDataMap] = useState<Map<string, any>>(new Map())
  const [forkDialogOpen, setForkDialogOpen] = useState(false)
  const [forkingBlockId, setForkingBlockId] = useState<string | null>(null)
  const [forkedBlocks, setForkedBlocks] = useState<Map<string, ForkedBlock>>(new Map())
  const {
    currentBlockId,
    setCurrentBlock,
    librarianSidebarOpen,
    setLibrarianSidebarOpen,
    patchSidebarOpen,
    setPatchSidebarOpen,
  } = useResearchStore()

  // Fetch claim data for all claim_ids in blocks
  useEffect(() => {
    if (!jobId) return

    const fetchClaimData = async () => {
      try {
        const response = await fetch(`/api/proxy/orchestrator/workflow/result/${jobId}`)
        if (!response.ok) return

        const data = await response.json()
        const result = data?.result || {}
        const extractedJson = result?.extracted_json || {}
        const triples = extractedJson?.triples || []

        // Build map of claim_id -> source_pointer
        const map = new Map()
        triples.forEach((triple: any, idx: number) => {
          const claimId = triple.claim_id || `claim-${idx}`
          if (triple.source_pointer) {
            map.set(claimId, triple.source_pointer)
          }
        })

        setClaimDataMap(map)
      } catch (err) {
        console.error("Failed to fetch claim data:", err)
      }
    }

    fetchClaimData()
  }, [jobId])

  useEffect(() => {
    setLocalBlocks(blocks)
  }, [blocks])

  const updateBlock = (id: string, patch: Partial<Block>) => {
    setLocalBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, ...patch } : b)))
  }

  const addBlock = () => {
    const newBlock: Block = {
      id: `block-${Date.now()}`,
      section_title: "",
      content: "",
      citation_keys: [],
      claim_ids: [],
    }
    setLocalBlocks((prev) => [...prev, newBlock])
    setCurrentBlock(newBlock.id)
  }

  const deleteBlock = (id: string) => {
    setLocalBlocks((prev) => prev.filter((b) => b.id !== id))
    if (currentBlockId === id) {
      setCurrentBlock(null)
    }
  }

  const activeBlock = localBlocks.find((b) => b.id === currentBlockId)

  const handleFork = async (rigorLevel: "exploratory" | "conservative") => {
    if (!forkingBlockId || !projectId) return

    const block = localBlocks.find((b) => b.id === forkingBlockId)
    if (!block) return

    try {
      const response = await fetch(
        `/api/proxy/orchestrator/api/projects/${projectId}/blocks/${block.block_id || block.id}/fork`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            rigor_level: rigorLevel,
            job_id: jobId,
          }),
        }
      )

      if (!response.ok) {
        throw new Error("Failed to fork block")
      }

      const data = await response.json()
      const forkedBlock = data.forked_block

      setForkedBlocks((prev) => {
        const next = new Map(prev)
        next.set(block.id, forkedBlock)
        return next
      })

      toast({
        title: "Block forked",
        description: `Alternate version generated with ${rigorLevel} rigor.`,
      })
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to fork block",
        variant: "destructive",
      })
    }
  }

  return (
    <div className="h-full flex">
      <ForkDialog
        open={forkDialogOpen}
        onClose={() => {
          setForkDialogOpen(false)
          setForkingBlockId(null)
        }}
        onFork={handleFork}
        currentRigor={activeBlock?.rigor_level}
      />
      {/* Main Editor Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="space-y-6 p-6">
          {localBlocks.map((block) => {
            const isActive = currentBlockId === block.id
            return (
              <Card
                key={block.id}
                className={cn(
                  "transition-all duration-200",
                  isActive ? "ring-2 ring-primary/20 bg-background" : "bg-muted/20"
                )}
              >
                <div className="p-6 space-y-4">
                  {/* Header with Ghost Mode Controls */}
                  <div className="flex items-center gap-3">
                    <Input
                      value={block.section_title}
                      onChange={(e) => updateBlock(block.id, { section_title: e.target.value })}
                      placeholder="Section title"
                      className="flex-1 text-lg font-semibold"
                      onFocus={() => setCurrentBlock(block.id)}
                    />
                    {isActive && (
                      <div className="flex items-center gap-2 animate-in fade-in duration-200">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteBlock(block.id)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Content Editor */}
                  <Textarea
                    value={block.content}
                    onChange={(e) => updateBlock(block.id, { content: e.target.value })}
                    rows={12}
                    placeholder="Write or paste content..."
                    className="text-lg leading-relaxed resize-none"
                    onFocus={() => setCurrentBlock(block.id)}
                  />

                  {/* Metadata: Claim IDs and Citation Keys */}
                  <div className="space-y-2 pt-2 border-t border-border/30">
                    <div className="flex items-center gap-2 flex-wrap text-xs">
                      {block.claim_ids.length > 0 ? (
                        <>
                          <span className="text-muted-foreground font-medium">Claims:</span>
                          {block.claim_ids.map((claimId) => (
                            <ClaimIdLink
                              key={claimId}
                              claimId={claimId}
                              sourcePointer={claimDataMap.get(claimId)}
                            />
                          ))}
                        </>
                      ) : (
                        <span className="text-muted-foreground">No claims linked</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap text-xs">
                      {block.citation_keys.length > 0 ? (
                        <>
                          <span className="text-muted-foreground font-medium">Citations:</span>
                          {block.citation_keys.map((key) => (
                            <Badge key={key} variant="outline" className="text-xs">
                              {key}
                            </Badge>
                          ))}
                        </>
                      ) : (
                        <span className="text-muted-foreground">No citations</span>
                      )}
                    </div>
                  </div>

                  {/* Actions: Accept / Reject / Notes */}
                  {isActive && (
                    <div className="flex items-center gap-2 pt-2 border-t border-border/30">
                      <Button
                        variant={block.status === "accepted" ? "default" : "outline"}
                        size="sm"
                        onClick={() => updateBlock(block.id, { status: "accepted" })}
                        className="text-xs"
                      >
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        Accept
                      </Button>
                      <Button
                        variant={block.status === "rejected" ? "destructive" : "outline"}
                        size="sm"
                        onClick={() => updateBlock(block.id, { status: "rejected" })}
                        className="text-xs"
                      >
                        <XCircle className="h-3 w-3 mr-1" />
                        Reject
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const notes = prompt("Add notes:", block.notes || "")
                          if (notes !== null) {
                            updateBlock(block.id, { notes })
                          }
                        }}
                        className="text-xs"
                      >
                        <MessageSquare className="h-3 w-3 mr-1" />
                        Notes
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setForkingBlockId(block.id)
                          setForkDialogOpen(true)
                        }}
                        className="text-xs"
                      >
                        <GitBranch className="h-3 w-3 mr-1" />
                        Fork
                      </Button>
                      {block.confidence !== undefined && (
                        <Badge
                          variant={
                            block.confidence >= 0.8
                              ? "default"
                              : block.confidence >= 0.5
                              ? "secondary"
                              : "outline"
                          }
                          className="text-xs ml-auto"
                        >
                          {block.confidence >= 0.8
                            ? "High"
                            : block.confidence >= 0.5
                            ? "Medium"
                            : "Low"}
                        </Badge>
                      )}
                    </div>
                  )}
                  
                  {/* Forked Block Display (Read-only) */}
                  {forkedBlocks.has(block.id) && (
                    <div className="mt-4 pt-4 border-t border-border/30">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="text-xs">
                            Fork ({forkedBlocks.get(block.id)?.rigor_level})
                          </Badge>
                          <span className="text-xs text-muted-foreground">Alternate version</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={async () => {
                              const forked = forkedBlocks.get(block.id)!
                              try {
                                const response = await fetch(
                                  `/api/proxy/orchestrator/api/projects/${projectId}/blocks/${block.block_id || block.id}/accept-fork`,
                                  {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({
                                      content: forked.content,
                                      section_title: forked.section_title,
                                      rigor_level: forked.rigor_level,
                                    }),
                                  }
                                )
                                if (!response.ok) {
                                  throw new Error("Failed to accept fork")
                                }
                                toast({
                                  title: "Fork accepted",
                                  description: "Block has been updated with the forked version.",
                                })
                                setForkedBlocks((prev) => {
                                  const next = new Map(prev)
                                  next.delete(block.id)
                                  return next
                                })
                              } catch (err) {
                                toast({
                                  title: "Error",
                                  description: "Failed to accept fork",
                                  variant: "destructive",
                                })
                              }
                            }}
                            className="text-xs"
                          >
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            Accept Fork
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setForkedBlocks((prev) => {
                                const next = new Map(prev)
                                next.delete(block.id)
                                return next
                              })
                            }}
                            className="text-xs"
                          >
                            <XCircle className="h-3 w-3 mr-1" />
                            Discard
                          </Button>
                        </div>
                      </div>
                      <div className="bg-muted/30 rounded-md p-4">
                        <div className="text-sm font-medium mb-2">
                          {forkedBlocks.get(block.id)?.section_title}
                        </div>
                        <div className="text-sm text-muted-foreground whitespace-pre-wrap">
                          {forkedBlocks.get(block.id)?.content}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            )
          })}

          {/* Add Block Button (only when no active block or at end) */}
          {(!currentBlockId || currentBlockId === localBlocks[localBlocks.length - 1]?.id) && (
            <Button
              variant="outline"
              className="w-full border-dashed"
              onClick={addBlock}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Block
            </Button>
          )}

          {localBlocks.length === 0 && (
            <Card className="p-12 text-center">
              <p className="text-sm text-muted-foreground mb-4">
                No manuscript blocks yet. Add blocks from the Manuscript Kernel.
              </p>
              <Button variant="outline" onClick={addBlock}>
                <Plus className="h-4 w-4 mr-2" />
                Create First Block
              </Button>
            </Card>
          )}
        </div>
      </div>

      {/* Collapsible Sidebars */}
      <div className="flex flex-col gap-2 border-l border-border/30 bg-muted/10">
        {/* Librarian (Citation) Sidebar */}
        <Collapsible open={librarianSidebarOpen} onOpenChange={setLibrarianSidebarOpen}>
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="w-12 h-12 rounded-none border-b border-border/30"
            >
              <BookOpen className="h-5 w-5" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="w-80 h-full bg-background border-l border-border/30">
              <div className="p-4 border-b border-border/30">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold">Librarian</h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setLibrarianSidebarOpen(false)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Citation validation and bibliography management
                </p>
              </div>
              <div className="p-4 space-y-2">
                {activeBlock?.citation_keys.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">Active Citations</p>
                    {activeBlock.citation_keys.map((key) => (
                      <Badge key={key} variant="outline" className="text-xs">
                        {key}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No citations in active block</p>
                )}
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Patch (AI Suggestions) Sidebar */}
        <Collapsible open={patchSidebarOpen} onOpenChange={setPatchSidebarOpen}>
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="w-12 h-12 rounded-none"
            >
              <FileEdit className="h-5 w-5" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="w-80 h-full bg-background border-l border-border/30">
              <div className="p-4 border-b border-border/30">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold">AI Suggestions</h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setPatchSidebarOpen(false)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Proposed edits and patches for review
                </p>
              </div>
              <div className="p-4">
                <p className="text-xs text-muted-foreground">No pending patches</p>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>
    </div>
  )
}

