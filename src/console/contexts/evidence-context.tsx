"use client"

/**
 * Evidence Context for cross-pane communication
 * Allows Manuscript Pane to trigger highlights in Evidence Pane
 */

import React, { createContext, useContext, useState, useCallback, ReactNode } from "react"

export type EvidenceCoordinates = {
  page: number
  bbox: {
    x1: number
    y1: number
    x2: number
    y2: number
  }
  doc_hash?: string
  snippet?: string
  claim_id?: string
}

interface EvidenceContextType {
  highlight: EvidenceCoordinates | null
  setHighlight: (coords: EvidenceCoordinates | null) => void
  clearHighlight: () => void
}

const EvidenceContext = createContext<EvidenceContextType | undefined>(undefined)

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const [highlight, setHighlightState] = useState<EvidenceCoordinates | null>(null)

  const setHighlight = useCallback((coords: EvidenceCoordinates | null) => {
    setHighlightState(coords)
    // Auto-clear after 3 seconds
    if (coords) {
      setTimeout(() => {
        setHighlightState((current) => (current === coords ? null : current))
      }, 3000)
    }
  }, [])

  const clearHighlight = useCallback(() => {
    setHighlightState(null)
  }, [])

  return (
    <EvidenceContext.Provider value={{ highlight, setHighlight, clearHighlight }}>
      {children}
    </EvidenceContext.Provider>
  )
}

export function useEvidence() {
  const context = useContext(EvidenceContext)
  if (!context) {
    throw new Error("useEvidence must be used within EvidenceProvider")
  }
  return context
}

