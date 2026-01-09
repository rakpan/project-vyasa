"use client"

/**
 * Citations Panel Component
 * 
 * Shows chunk provenance and retrieval bundle link for a manuscript block.
 * Displays:
 * - Chunk IDs with page numbers and source
 * - Retrieval Bundle ID (linkable)
 * - Model IDs used (embedder, reranker, synthesizer, critic)
 */

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ExternalLink, FileText, Database, Cpu } from "lucide-react"
import { cn } from "@/lib/utils"

interface CitationsPanelProps {
  blockId?: string
  projectId: string
  retrievalBundleId?: string
  chunkIds?: string[]
  modelIds?: Record<string, string>
}

interface ChunkInfo {
  chunk_id: string
  page_number?: number
  file_hash?: string
  source_filename?: string
  text_preview?: string
  ingestion_id?: string
  chunk_index?: number
  bbox?: Record<string, number>
}

export function CitationsPanel({
  blockId,
  projectId,
  retrievalBundleId,
  chunkIds = [],
  modelIds = {},
}: CitationsPanelProps) {
  const [chunks, setChunks] = useState<ChunkInfo[]>([])
  const [isLoading, setIsLoading] = useState(false)

  // Fetch chunk details if chunkIds provided
  useEffect(() => {
    if (!chunkIds || chunkIds.length === 0) {
      setChunks([])
      return
    }

    const fetchChunks = async () => {
      setIsLoading(true)
      try {
        // Call endpoint to fetch chunk metadata
        const chunkIdsParam = chunkIds.join(",")
        const response = await fetch(
          `/api/proxy/orchestrator/api/projects/${projectId}/chunks?chunk_ids=${encodeURIComponent(chunkIdsParam)}`
        )
        
        if (!response.ok) {
          throw new Error(`Failed to fetch chunks: ${response.status}`)
        }
        
        const data = await response.json()
        const chunkInfos: ChunkInfo[] = (data.chunks || []).map((chunk: any) => ({
          chunk_id: chunk.chunk_id,
          page_number: chunk.page_number,
          file_hash: chunk.file_hash,
          source_filename: chunk.source_filename,
          text_preview: chunk.text_preview,
          ingestion_id: chunk.ingestion_id,
          chunk_index: chunk.chunk_index,
          bbox: chunk.bbox,
        }))
        
        setChunks(chunkInfos)
      } catch (error) {
        console.error("Failed to fetch chunk details:", error)
        // On error, still set empty chunks to avoid showing stale data
        setChunks([])
      } finally {
        setIsLoading(false)
      }
    }

    fetchChunks()
  }, [chunkIds, projectId])

  if (!blockId && !retrievalBundleId && chunkIds.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Citations</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">Select a block to view citations</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="border-b">
        <CardTitle className="text-sm">Citations & Provenance</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col p-4 min-h-0">
        <ScrollArea className="flex-1">
          <div className="space-y-4">
            {/* Retrieval Bundle */}
            {retrievalBundleId && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs font-semibold">Retrieval Bundle</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="text-xs bg-muted px-2 py-1 rounded font-mono">
                    {retrievalBundleId}
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs"
                    onClick={() => {
                      // TODO: Navigate to retrieval bundle detail view
                      console.log("View retrieval bundle:", retrievalBundleId)
                    }}
                  >
                    <ExternalLink className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            )}

            {/* Chunks */}
            {chunkIds.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs font-semibold">
                    Evidence Chunks ({chunkIds.length})
                  </span>
                </div>
                {isLoading ? (
                  <div className="text-xs text-muted-foreground">Loading chunk details...</div>
                ) : chunks.length > 0 ? (
                  <div className="space-y-2">
                    {chunks.map((chunk) => (
                      <div
                        key={chunk.chunk_id}
                        className="p-2 bg-muted/50 rounded text-xs border border-border"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <code className="font-mono text-[10px] break-all">{chunk.chunk_id}</code>
                        </div>
                        {chunk.source_filename && (
                          <div className="mt-1 text-muted-foreground font-medium">
                            {chunk.source_filename}
                          </div>
                        )}
                        {chunk.page_number && (
                          <div className="mt-1 text-muted-foreground">
                            Page {chunk.page_number}
                          </div>
                        )}
                        {chunk.text_preview && (
                          <div className="mt-2 text-muted-foreground line-clamp-2 text-xs">
                            {chunk.text_preview}
                          </div>
                        )}
                        {chunk.ingestion_id && (
                          <div className="mt-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 text-xs"
                              onClick={() => {
                                // TODO: Navigate to Evidence Dock with this chunk highlighted
                                console.log("View in Evidence Dock:", chunk.ingestion_id, chunk.chunk_id)
                              }}
                            >
                              <ExternalLink className="h-3 w-3 mr-1" />
                              View in Evidence Dock
                            </Button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-muted-foreground">
                    Chunk details not available
                  </div>
                )}
              </div>
            )}

            {/* Model IDs */}
            {Object.keys(modelIds).length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Cpu className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs font-semibold">Models Used</span>
                </div>
                <div className="space-y-1">
                  {Object.entries(modelIds).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {key}
                      </Badge>
                      <code className="text-[10px] text-muted-foreground font-mono">
                        {value}
                      </code>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!retrievalBundleId && chunkIds.length === 0 && Object.keys(modelIds).length === 0 && (
              <div className="text-xs text-muted-foreground text-center py-4">
                No citation data available
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
