/**
 * Claim type definitions for Knowledge Pane
 */

export type ClaimStatus = "Proposed" | "Flagged" | "Accepted" | "Needs Review"

export interface ClaimProvenance {
  proposed_by: string // e.g., "Cartographer"
  verified_by: string | null // e.g., "Brain"
  flagged_by: string | null // e.g., "Critic"
}

export interface SourcePointer {
  doc_hash?: string
  page?: number
  bbox?: [number, number, number, number]
  snippet?: string
}

export interface ConflictData {
  conflictId: string
  summary: string // Backend-provided explanation
  details?: string
  sourceA: SourcePointer
  sourceB: SourcePointer
  claimA?: string // Conflicting claim text from source A
  claimB?: string // Conflicting claim text from source B
}

export interface Claim {
  id: string
  text: string // Full claim text
  shortText: string // Shortened version for display
  subject: string
  predicate: string
  object: string
  confidence?: number
  status: ClaimStatus
  provenance: ClaimProvenance
  linkedRQ: string | null // Linked research question
  sourcePointer: SourcePointer
  evidence: string
  flags: string[] // Conflict flags
  citations: string[] // Citation keys
  conflictData?: ConflictData // Conflict details if flagged
}

