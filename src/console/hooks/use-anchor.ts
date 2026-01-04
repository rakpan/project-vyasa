/**
 * use-anchor hook for managing context anchor state
 * 
 * Provides scrollToAnchor functionality for evidence pane navigation
 */

import { useCallback, useState } from "react"
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
  const [activeAnchor, setActiveAnchor] = useState<SourceAnchor | null>(null)

  const activateAnchor = useCallback(
    (anchor: SourceAnchor | null) => {
      setActiveAnchor(anchor)
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

  const activateClaim = useCallback(
    async (claimId: string) => {
      try {
        const response = await fetch(`/api/proxy/orchestrator/api/claims/${claimId}/anchor`)
        if (!response.ok) {
          if (response.status === 404) {
            console.warn(`Claim ${claimId} not found`)
            return
          }
          throw new Error(`Failed to fetch anchor: ${response.statusText}`)
        }
        
        const data = await response.json()
        if (data.source_anchor) {
          activateAnchor(data.source_anchor)
        } else {
          console.warn(`No source_anchor found for claim ${claimId}`)
        }
      } catch (error) {
        console.error(`Failed to activate claim ${claimId}:`, error)
      }
    },
    [activateAnchor]
  )

  const scrollToAnchor = useCallback(
    (anchor: SourceAnchor | null) => {
      activateAnchor(anchor)
    },
    [activateAnchor]
  )

  return {
    activeAnchor,
    activateAnchor,
    activateClaim,
    scrollToAnchor,
  }
}

