"use client"

import * as React from "react"
import { useState, useRef, useEffect } from "react"
import { Worker, Viewer, SpecialZoomLevel } from "@react-pdf-viewer/core"
import { highlightPlugin } from "@react-pdf-viewer/highlight"
import "@react-pdf-viewer/core/lib/styles/index.css"
import "@react-pdf-viewer/highlight/lib/styles/index.css"
import { Button } from "@/components/ui/button"
import { ZoomIn, ZoomOut, RotateCw, Maximize2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Scan } from "lucide-react"

type EvidenceCoordinates = {
  page: number
  bbox: {
    x1: number
    y1: number
    x2: number
    y2: number
  }
  doc_hash?: string
  snippet?: string
}

type ZenSourceVaultProps = {
  fileUrl: string
  highlight?: EvidenceCoordinates | null
  workerUrl?: string
  onRescan?: (coords: EvidenceCoordinates) => void
}

function toHighlightArea(coords: EvidenceCoordinates | null | undefined) {
  if (!coords) return []
  const { page, bbox } = coords
  const normalize = (v: number) => Math.max(0, Math.min(1, v / 1000))
  const left = normalize(bbox.x1)
  const top = normalize(bbox.y1)
  const right = normalize(bbox.x2)
  const bottom = normalize(bbox.y2)
  return [
    {
      pageIndex: Math.max(0, page - 1),
      left,
      top,
      width: Math.max(0.01, right - left),
      height: Math.max(0.01, bottom - top),
      color: "rgba(255, 210, 0, 0.35)",
    },
  ]
}

/**
 * Source Vault with auto-hide toolbars and floating selection tool.
 * Zen-First: Controls appear only when needed.
 */
export function ZenSourceVault({ fileUrl, highlight, workerUrl, onRescan }: ZenSourceVaultProps) {
  const [areas, setAreas] = React.useState(() => toHighlightArea(highlight))
  const [showToolbar, setShowToolbar] = useState(false)
  const [selectionCoords, setSelectionCoords] = useState<EvidenceCoordinates | null>(null)
  const [isSelecting, setIsSelecting] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const startCoordsRef = useRef<{ x: number; y: number } | null>(null)

  const highlightPluginInstance = React.useMemo(
    () =>
      highlightPlugin({
        renderHighlights: (props) => {
          const area = areas.find((a) => a.pageIndex === props.pageIndex)
          if (!area) return <></>
          const style = props.getCssProperties(area, props.rotation)
          return (
            <div
              key={`highlight-${props.pageIndex}`}
              style={{
                ...style,
                backgroundColor: area.color,
                border: "1px solid rgba(255, 210, 0, 0.8)",
                pointerEvents: "none",
              }}
            />
          )
        },
      }),
    [areas]
  )

  // Simple zoom state (zoom plugin may not be available)
  const [scale, setScale] = useState(100)

  React.useEffect(() => {
    const nextAreas = toHighlightArea(highlight)
    setAreas(nextAreas)
    if (highlight && highlightPluginInstance.jumpToHighlightArea && nextAreas[0]) {
      highlightPluginInstance.jumpToHighlightArea(nextAreas[0])
    }
  }, [highlight, highlightPluginInstance])

  // Auto-hide toolbar on hover over top 10%
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect()
      const relativeY = e.clientY - rect.top
      const topPercent = (relativeY / rect.height) * 100
      setShowToolbar(topPercent <= 10)
    }

    container.addEventListener("mousemove", handleMouseMove)
    return () => container.removeEventListener("mousemove", handleMouseMove)
  }, [])

  // Selection tool (bounding box)
  const handleMouseDown = (e: React.MouseEvent) => {
    if (!containerRef.current || !onRescan) return
    e.preventDefault()
    const rect = containerRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    startCoordsRef.current = { x, y }
    setIsSelecting(true)
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isSelecting || !startCoordsRef.current || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    // Update selection preview (could show a rectangle overlay)
  }

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!isSelecting || !startCoordsRef.current || !containerRef.current || !onRescan) {
      setIsSelecting(false)
      return
    }

    const rect = containerRef.current.getBoundingClientRect()
    const endX = e.clientX - rect.left
    const endY = e.clientY - rect.top

    const norm = (v: number) => Math.round(Math.max(0, Math.min(1, v / rect.width)) * 1000)
    const normY = (v: number) => Math.round(Math.max(0, Math.min(1, v / rect.height)) * 1000)

    const coords: EvidenceCoordinates = {
      page: 1, // TODO: Get current page
      bbox: {
        x1: norm(startCoordsRef.current.x),
        y1: normY(startCoordsRef.current.y),
        x2: norm(endX),
        y2: normY(endY),
      },
      snippet: "",
      doc_hash: "",
    }

    setSelectionCoords(coords)
    setIsSelecting(false)
    startCoordsRef.current = null
  }

  return (
    <div
      ref={containerRef}
      className="h-full relative bg-muted/20"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {/* Auto-hide toolbar */}
      <div
        className={cn(
          "absolute top-0 left-0 right-0 z-20 bg-background/95 backdrop-blur-sm border-b border-border/30 transition-opacity duration-200",
          showToolbar ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
      >
        <div className="flex items-center gap-2 px-4 py-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setScale(Math.max(50, scale - 10))}
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground min-w-[60px] text-center">
            {scale}%
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setScale(Math.min(200, scale + 10))}
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* PDF Viewer */}
      {fileUrl ? (
        <Worker workerUrl={workerUrl || "https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js"}>
          <Viewer
            fileUrl={fileUrl}
            plugins={[highlightPluginInstance]}
            defaultScale={SpecialZoomLevel.PageFit}
          />
        </Worker>
      ) : (
        <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
          Select a document to view
        </div>
      )}

      {/* Floating Selection Tool (appears after selection) */}
      {selectionCoords && (
        <Popover open={!!selectionCoords} onOpenChange={(open) => !open && setSelectionCoords(null)}>
          <PopoverTrigger asChild>
            <Button
              className="absolute bottom-4 right-4 shadow-lg"
              size="sm"
              variant="default"
            >
              <Scan className="h-4 w-4 mr-2" />
              Rescan Selection
            </Button>
          </PopoverTrigger>
          <PopoverContent side="left" className="w-64">
            <div className="space-y-2">
              <p className="text-sm font-medium">Rescan Selected Area</p>
              <p className="text-xs text-muted-foreground">
                Re-extract knowledge from the selected region
              </p>
              <Button
                size="sm"
                className="w-full"
                onClick={() => {
                  if (selectionCoords && onRescan) {
                    onRescan(selectionCoords)
                    setSelectionCoords(null)
                  }
                }}
              >
                Confirm Rescan
              </Button>
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  )
}

