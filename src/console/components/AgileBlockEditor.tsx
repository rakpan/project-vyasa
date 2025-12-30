"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useResearchStore } from "@/state/useResearchStore"

type Block = {
  id: string
  section_title: string
  content: string
  citation_keys: string[]
}

type AgileBlockEditorProps = {
  projectId?: string
  blocks?: Block[]
}

export function AgileBlockEditor({ projectId, blocks = [] }: AgileBlockEditorProps) {
  const [localBlocks, setLocalBlocks] = useState<Block[]>(blocks)
  const { currentBlockId, setCurrentBlock } = useResearchStore()

  useEffect(() => {
    setLocalBlocks(blocks)
  }, [blocks])

  const updateBlock = (id: string, patch: Partial<Block>) => {
    setLocalBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, ...patch } : b)))
  }

  return (
    <div className="h-full overflow-y-auto space-y-3 p-3">
      {localBlocks.map((block) => (
        <Card key={block.id} className="p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Input
              value={block.section_title}
              onChange={(e) => updateBlock(block.id, { section_title: e.target.value })}
              placeholder="Section title"
              className="flex-1"
            />
            <Button variant={currentBlockId === block.id ? "default" : "outline"} size="sm" onClick={() => setCurrentBlock(block.id)}>
              Focus
            </Button>
          </div>
          <Textarea
            value={block.content}
            onChange={(e) => updateBlock(block.id, { content: e.target.value })}
            rows={8}
            placeholder="Write or paste content..."
          />
          <div className="text-xs text-muted-foreground">Citations: {block.citation_keys.join(", ") || "none"}</div>
        </Card>
      ))}
      {localBlocks.length === 0 && (
        <Card className="p-4 text-sm text-muted-foreground">No manuscript blocks yet. Add blocks from the Manuscript Kernel.</Card>
      )}
    </div>
  )
}
