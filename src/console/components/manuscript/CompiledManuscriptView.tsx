"use client"

/**
 * Compiled Manuscript View Component
 * 
 * Renders manuscript blocks from section runs in a compiled view:
 * - hook/proof/so-what blocks (if split)
 * - visual placeholders (table/figure) as callouts
 * - Citations panel showing chunk provenance + retrieval bundle link
 */

import React, { useState, useEffect, ReactNode } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Image, Table, FileText, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import { CitationsPanel } from "./CitationsPanel"

interface ManuscriptBlock {
  block_id: string
  section_title: string
  content: string
  section_id?: string
  order_index: number
  claim_ids: string[]
  citation_keys: string[]
  retrieval_bundle_id?: string
  chunk_ids: string[]
  note_ids: string[]
  model_ids: Record<string, string>
  created_at?: string
}

interface VisualAnchor {
  anchor_id: string
  anchor_type: "table" | "figure" | "equation"
  placeholder_text: string
}

interface CompiledManuscriptViewProps {
  projectId: string
  sectionId?: string
  onBlockSelect?: (blockId: string) => void
  selectedBlockId?: string
}

export function CompiledManuscriptView({
  projectId,
  sectionId,
  onBlockSelect,
  selectedBlockId,
}: CompiledManuscriptViewProps) {
  const [blocks, setBlocks] = useState<ManuscriptBlock[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedBlock, setSelectedBlock] = useState<ManuscriptBlock | null>(null)

  // Fetch blocks
  useEffect(() => {
    const fetchBlocks = async () => {
      setIsLoading(true)
      try {
        let url = `/api/proxy/orchestrator/api/projects/${projectId}/manuscript/blocks`
        if (sectionId) {
          url += `?section_id=${sectionId}`
        }
        const response = await fetch(url)
        if (response.ok) {
          const data = await response.json()
          setBlocks(Array.isArray(data) ? data : [])
        } else {
          setBlocks([])
        }
      } catch (error) {
        console.error("Failed to fetch blocks:", error)
        setBlocks([])
      } finally {
        setIsLoading(false)
      }
    }

    if (projectId) {
      fetchBlocks()
    }
  }, [projectId, sectionId])

  // Update selected block when selectedBlockId changes
  useEffect(() => {
    if (selectedBlockId) {
      const block = blocks.find((b) => b.block_id === selectedBlockId)
      setSelectedBlock(block || null)
    } else {
      setSelectedBlock(null)
    }
  }, [selectedBlockId, blocks])

  // Group blocks by section
  const blocksBySection = blocks.reduce((acc, block) => {
    const sectionKey = block.section_id || "unknown"
    if (!acc[sectionKey]) {
      acc[sectionKey] = []
    }
    acc[sectionKey].push(block)
    return acc
  }, {} as Record<string, ManuscriptBlock[]>)

  // Sort blocks within each section by order_index
  Object.keys(blocksBySection).forEach((sectionKey) => {
    blocksBySection[sectionKey].sort((a, b) => a.order_index - b.order_index)
  })

  // Process text to highlight citation markers
  const processCitationMarkers = (text: string): ReactNode[] => {
    // Match citation markers: [[chunk:<id>]], [[claim:<id>]], or simple [[<id>]]
    const citationRegex = /\[\[(?:chunk:|claim:)?([^\]]+)\]\]/g
    const parts: ReactNode[] = []
    let lastIndex = 0
    let match

    while ((match = citationRegex.exec(text)) !== null) {
      // Add text before citation
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index))
      }
      
      // Add highlighted citation
      const citationId = match[1]
      const fullMatch = match[0]
      parts.push(
        <span
          key={`citation-${match.index}`}
          className="text-primary font-mono text-xs bg-primary/10 px-1.5 py-0.5 rounded cursor-pointer hover:bg-primary/20 transition-colors"
          title={`Citation: ${citationId}`}
        >
          {fullMatch}
        </span>
      )
      
      lastIndex = match.index + match[0].length
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex))
    }

    return parts.length > 0 ? parts : [text]
  }

  // Recursively process children to highlight citations
  const processChildren = (children: ReactNode): ReactNode => {
    if (typeof children === "string") {
      return processCitationMarkers(children)
    }
    
    if (Array.isArray(children)) {
      return children.map((child, idx) => (
        <React.Fragment key={idx}>{processChildren(child)}</React.Fragment>
      ))
    }
    
    if (React.isValidElement(children) && children.props.children) {
      return React.cloneElement(children, {
        ...children.props,
        children: processChildren(children.props.children),
      })
    }
    
    return children
  }

  // Render visual placeholder
  const renderVisualPlaceholder = (type: string, anchorId: string, description?: string) => {
    const Icon = type === "table" ? Table : type === "figure" ? Image : FileText
    const displayText = description || `Spec not provided for ${anchorId}`
    return (
      <Card className="border-dashed border-2 border-muted-foreground/30 bg-muted/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-muted rounded">
              <Icon className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="flex-1">
              <Badge variant="outline" className="mb-2 text-xs">
                {type.toUpperCase()} PLACEHOLDER
              </Badge>
              <p className="text-xs font-mono text-muted-foreground mb-1">ID: {anchorId}</p>
              <p className="text-sm text-muted-foreground">{displayText}</p>
              <p className="text-xs text-muted-foreground mt-2 italic">
                This {type} will be generated or inserted manually.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Parse content for visual placeholders and markdown
  const parseBlockContent = (content: string) => {
    // Check for visual placeholder markers: [[FIGURE:<anchor_id>]] or [[TABLE:<anchor_id>]]
    const visualPlaceholderRegex = /\[\[(FIGURE|TABLE):([^\]]+)\]\]/g
    const parts: Array<{ type: "markdown" | "visual"; content: string; visualType?: string; anchorId?: string }> = []
    let lastIndex = 0
    let match

    while ((match = visualPlaceholderRegex.exec(content)) !== null) {
      // Add markdown before placeholder
      if (match.index > lastIndex) {
        parts.push({
          type: "markdown",
          content: content.substring(lastIndex, match.index),
        })
      }
      // Add visual placeholder
      const markerType = match[1] // "FIGURE" or "TABLE"
      const anchorId = match[2] // anchor_id
      const visualType = markerType.toLowerCase() // "figure" or "table"
      parts.push({
        type: "visual",
        content: `Placeholder for ${visualType} (${anchorId})`, // Default description
        visualType: visualType,
        anchorId: anchorId,
      })
      lastIndex = match.index + match[0].length
    }

    // Add remaining markdown
    if (lastIndex < content.length) {
      parts.push({
        type: "markdown",
        content: content.substring(lastIndex),
      })
    }

    // If no placeholders found, return entire content as markdown
    if (parts.length === 0) {
      return [{ type: "markdown" as const, content }]
    }

    return parts
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">Loading manuscript blocks...</p>
        </div>
      </div>
    )
  }

  if (blocks.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-sm font-semibold mb-2">No manuscript blocks yet</p>
          <p className="text-xs text-muted-foreground">
            Run a section from the blueprint to generate blocks
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex gap-4">
      {/* Main Editor Area */}
      <div className="flex-1 flex flex-col min-h-0">
        <ScrollArea className="flex-1">
          <div className="p-6 space-y-6">
            {Object.entries(blocksBySection).map(([sectionKey, sectionBlocks]) => (
              <div key={sectionKey} className="space-y-4">
                {sectionBlocks.map((block) => {
                  const isSelected = selectedBlockId === block.block_id
                  const contentParts = parseBlockContent(block.content)

                  return (
                    <Card
                      key={block.block_id}
                      className={cn(
                        "transition-all duration-200 cursor-pointer",
                        isSelected && "ring-2 ring-primary"
                      )}
                      onClick={() => {
                        setSelectedBlock(block)
                        onBlockSelect?.(block.block_id)
                      }}
                    >
                      <CardContent className="p-6 space-y-4">
                        {/* Section Title */}
                        <div>
                          <h3 className="text-lg font-semibold">{block.section_title}</h3>
                          {block.section_id && (
                            <Badge variant="outline" className="text-xs mt-1">
                              Section ID: {block.section_id.substring(0, 8)}...
                            </Badge>
                          )}
                        </div>

                        <Separator />

                        {/* Content */}
                        <div className="prose prose-sm max-w-none">
                          {contentParts.map((part, idx) => {
                            if (part.type === "visual" && part.visualType && part.anchorId) {
                              return (
                                <div key={idx} className="my-4">
                                  {renderVisualPlaceholder(part.visualType, part.anchorId, part.content)}
                                </div>
                              )
                            } else {
                              return (
                                <div key={idx} className="prose prose-sm max-w-none">
                                  <ReactMarkdown
                                    components={{
                                      // Process paragraph children to highlight citations
                                      p: ({ children, ...props }) => (
                                        <p className="mb-4 last:mb-0" {...props}>
                                          {processChildren(children)}
                                        </p>
                                      ),
                                      // Process text nodes directly for inline citations
                                      text: ({ children, ...props }) => {
                                        if (typeof children === "string") {
                                          return <>{processCitationMarkers(children)}</>
                                        }
                                        return <>{children}</>
                                      },
                                    }}
                                  >
                                    {part.content}
                                  </ReactMarkdown>
                                </div>
                              )
                            }
                          })}
                        </div>

                        {/* Metadata */}
                        <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t">
                          {block.claim_ids.length > 0 && (
                            <span>{block.claim_ids.length} claim{block.claim_ids.length !== 1 ? "s" : ""}</span>
                          )}
                          {block.chunk_ids.length > 0 && (
                            <span>{block.chunk_ids.length} chunk{block.chunk_ids.length !== 1 ? "s" : ""}</span>
                          )}
                          {block.created_at && (
                            <span>{new Date(block.created_at).toLocaleDateString()}</span>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Citations Panel (Right Sidebar) */}
      {selectedBlock && (
        <div className="w-80 flex-shrink-0">
          <CitationsPanel
            blockId={selectedBlock.block_id}
            projectId={projectId}
            retrievalBundleId={selectedBlock.retrieval_bundle_id}
            chunkIds={selectedBlock.chunk_ids}
            modelIds={selectedBlock.model_ids}
          />
        </div>
      )}
    </div>
  )
}
