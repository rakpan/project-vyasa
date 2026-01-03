/**
 * use-anchor hook for managing context anchor state
 * 
 * Provides scrollToAnchor functionality for evidence pane navigation
 */

import { useCallback } from "react"
import { useEvidence } from "@/contexts/evidence-context"
import type { EvidenceCoordinates } from "@/contexts/evidence-context"

export interface SourceAnchor {
  doc_id: string
  page_number: number
  span?: {
    start: number
    end: number
  }
  bbox?: {
    x: number
    y: number
    w: number
    h: number
  }
  snippet?: string
}

export function useAnchor() {
  const { setHighlight } = useEvidence()

  const scrollToAnchor = useCallback(
    (anchor: SourceAnchor | null) => {
      if (!anchor) {
        return
      }

      // Convert source_anchor to EvidenceCoordinates format
      const coords: EvidenceCoordinates = {
        page: anchor.page_number,
        bbox: anchor.bbox
          ? {
              x1: anchor.bbox.x,
              y1: anchor.bbox.y,
              x2: anchor.bbox.x + anchor.bbox.w,
              y2: anchor.bbox.y + anchor.bbox.h,
            }
          : {
              x1: 0,
              y1: 0,
              x2: 100,
              y2: 100,
            },
        doc_hash: anchor.doc_id,
        snippet: anchor.snippet,
      }

      setHighlight(coords)
    },
    [setHighlight]
  )

  return {
    scrollToAnchor,
  }
}

