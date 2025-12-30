"use client"

import * as React from "react"
import { Worker, Viewer, SpecialZoomLevel } from "@react-pdf-viewer/core"
import { highlightPlugin } from "@react-pdf-viewer/highlight"
import "@react-pdf-viewer/core/lib/styles/index.css"
import "@react-pdf-viewer/highlight/lib/styles/index.css"
import { Card } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useCallback, useRef } from "react"

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

type PdfVerificationViewProps = {
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

export function PdfVerificationView({ fileUrl, highlight, workerUrl, onRescan }: PdfVerificationViewProps) {
  const [areas, setAreas] = React.useState(() => toHighlightArea(highlight))
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
  const containerRef = useRef<HTMLDivElement | null>(null)

  React.useEffect(() => {
    const nextAreas = toHighlightArea(highlight)
    setAreas(nextAreas)
    if (highlight && highlightPluginInstance.jumpToHighlightArea && nextAreas[0]) {
      highlightPluginInstance.jumpToHighlightArea(nextAreas[0])
    }
  }, [highlight, highlightPluginInstance])

  const renderHighlightTarget = React.useCallback(
    (props: RenderHighlightTargetProps) => {
      const area = areas.find((a) => a.pageIndex === props.pageIndex)
      if (!area) return <></>
      const { left, top, width, height, color } = area
      return (
        <div
          style={{
            position: "absolute",
            left: `${left * 100}%`,
            top: `${top * 100}%`,
            width: `${width * 100}%`,
            height: `${height * 100}%`,
            background: color,
            pointerEvents: "none",
            border: "1px solid rgba(255, 210, 0, 0.8)",
          }}
        />
      )
    },
    [areas]
  )

  return (
    <Card className="h-full overflow-hidden" ref={containerRef}>
      {fileUrl ? (
        <Worker workerUrl={workerUrl || "https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js"}>
          <Viewer
            fileUrl={fileUrl}
            plugins={[highlightPluginInstance]}
            defaultScale={SpecialZoomLevel.PageFit}
            renderPage={(props) => {
              const handleContextMenu = (evt: React.MouseEvent) => {
                if (!onRescan || !containerRef.current) return
                evt.preventDefault()
                const rect = containerRef.current.getBoundingClientRect()
                const relX = (evt.clientX - rect.left) / rect.width
                const relY = (evt.clientY - rect.top) / rect.height
                const norm = (v: number) => Math.round(Math.max(0, Math.min(1, v)) * 1000)
                const coords: EvidenceCoordinates = {
                  page: props.pageIndex + 1,
                  bbox: { x1: norm(relX), y1: norm(relY), x2: norm(relX + 0.05), y2: norm(relY + 0.05) },
                  snippet: "",
                  doc_hash: "",
                }
                onRescan(coords)
              }
              return (
                <div onContextMenu={handleContextMenu}>
                  {props.canvasLayer.children}
                  {props.textLayer.children}
                  {props.annotationLayer.children}
                </div>
              )
            }}
          />
        </Worker>
      ) : (
        <Alert className="m-4">
          <AlertDescription>Select a claim to view its source snippet.</AlertDescription>
        </Alert>
      )}
    </Card>
  )
}
