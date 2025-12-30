"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Plus, Trash2, BookOpen, FileEdit, X } from "lucide-react"
import { useResearchStore } from "@/state/useResearchStore"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"

type Block = {
  id: string
  section_title: string
  content: string
  citation_keys: string[]
  claim_ids: string[]
  confidence?: number
  created_at?: string
}

type ZenManuscriptEditorProps = {
  projectId?: string
  blocks?: Block[]
}

/**
 * Zen-First Manuscript Editor with Ghost Mode and Collapsible Sidebars.
 * - Add/Delete buttons only appear on active block
 * - Librarian (Citation) and Patch (AI Suggestions) sidebars are collapsible
 */
export function ZenManuscriptEditor({ projectId, blocks = [] }: ZenManuscriptEditorProps) {
  const [localBlocks, setLocalBlocks] = useState<Block[]>(blocks)
  const {
    currentBlockId,
    setCurrentBlock,
    librarianSidebarOpen,
    setLibrarianSidebarOpen,
    patchSidebarOpen,
    setPatchSidebarOpen,
  } = useResearchStore()

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

  return (
    <div className="h-full flex">
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

                  {/* Metadata (small and muted) */}
                  <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-border/30">
                    <div className="flex items-center gap-4">
                      <span>
                        Citations: {block.citation_keys.length > 0 ? block.citation_keys.join(", ") : "none"}
                      </span>
                      <span>Claims: {block.claim_ids.length}</span>
                      {block.created_at && (
                        <span>{new Date(block.created_at).toLocaleDateString()}</span>
                      )}
                    </div>
                    {block.confidence !== undefined && (
                      <Badge
                        variant={
                          block.confidence >= 0.8
                            ? "default"
                            : block.confidence >= 0.5
                            ? "secondary"
                            : "outline"
                        }
                        className="text-xs"
                      >
                        {block.confidence >= 0.8
                          ? "High"
                          : block.confidence >= 0.5
                          ? "Medium"
                          : "Low"}
                      </Badge>
                    )}
                  </div>
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

