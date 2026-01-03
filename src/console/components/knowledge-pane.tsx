"use client"

/**
 * Knowledge Pane Component
 * Displays claims with provenance breadcrumbs and status flags
 * Shows agentic transparency without overwhelming the user
 */

import { useState, useEffect, useMemo } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { ClaimItem } from "./claim-item"
import { ClaimDetailDrawer } from "./claim-detail-drawer"
import type { Claim } from "@/types/claim"

interface KnowledgePaneProps {
  jobId: string
  projectId: string
  researchQuestions?: string[]
}

export function KnowledgePane({ jobId, projectId, researchQuestions = [] }: KnowledgePaneProps) {
  const [claims, setClaims] = useState<Claim[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)
  const [filterRQ, setFilterRQ] = useState<string | null>(null)

  // Fetch claims from job result
  useEffect(() => {
    if (!jobId) {
      setIsLoading(false)
      return
    }

    const fetchClaims = async () => {
      try {
        setIsLoading(true)
        const response = await fetch(`/api/proxy/orchestrator/workflow/result/${jobId}`)
        if (!response.ok) {
          throw new Error(`Failed to fetch job result: ${response.status}`)
        }

        const data = await response.json()
        const result = data?.result || {}
        const extractedJson = result?.extracted_json || {}
        const triples = extractedJson?.triples || []

        // Fetch conflict report if available
        let conflictReport: any = null
        try {
          const conflictResponse = await fetch(`/api/proxy/orchestrator/api/jobs/${jobId}/conflict-report`)
          if (conflictResponse.ok) {
            conflictReport = await conflictResponse.json()
          }
        } catch (err) {
          // Ignore errors - conflict report is optional
          console.debug("No conflict report available:", err)
        }

        // Build conflict map from conflict report
        const conflictMap = new Map<string, any>()
        if (conflictReport?.conflict_items) {
          conflictReport.conflict_items.forEach((item: any) => {
            // Map conflict to claim IDs or evidence anchors
            if (item.evidence_anchors && item.evidence_anchors.length >= 2) {
              // Use first anchor's doc_hash as key (could be claim ID or doc_hash+page)
              const key = item.evidence_anchors[0]?.doc_hash || item.conflict_id
              conflictMap.set(key, item)
            }
          })
        }

        // Transform triples to claims with provenance
        const transformedClaims: Claim[] = triples.map((triple: any, idx: number) => {
          // Extract provenance from triple metadata or infer from workflow
          const provenance = triple.provenance || {
            proposed_by: "Cartographer",
            verified_by: triple.is_expert_verified ? "Brain" : null,
            flagged_by: triple.conflict_flags?.length > 0 ? "Critic" : null,
          }

          // Determine status
          let status: Claim["status"] = "Proposed"
          if (triple.conflict_flags && triple.conflict_flags.length > 0) {
            status = "Flagged"
          } else if (triple.is_expert_verified) {
            status = "Accepted"
          } else if (triple.needs_review) {
            status = "Needs Review"
          }

          // Link to RQ if available (simple matching for now)
          const linkedRQ = researchQuestions.find((rq) =>
            triple.subject?.toLowerCase().includes(rq.toLowerCase().substring(0, 10)) ||
            triple.object?.toLowerCase().includes(rq.toLowerCase().substring(0, 10))
          ) || null

          // Extract conflict data if available
          let conflictData: Claim["conflictData"] = undefined
          if (triple.conflict_flags && triple.conflict_flags.length > 0) {
            // Try to find conflict item for this triple
            const conflictKey = triple.source_pointer?.doc_hash || triple.claim_id || `claim-${idx}`
            const conflictItem = conflictMap.get(conflictKey)
            
            if (conflictItem && conflictItem.evidence_anchors && conflictItem.evidence_anchors.length >= 2) {
              conflictData = {
                conflictId: conflictItem.conflict_id || `conflict-${idx}`,
                summary: conflictItem.summary || "Source A asserts this claim, while Source B contradicts it.",
                details: conflictItem.details,
                sourceA: conflictItem.evidence_anchors[0] || triple.source_pointer || {},
                sourceB: conflictItem.evidence_anchors[1] || {},
                claimA: triple.text || `${triple.subject} ${triple.predicate} ${triple.object}`,
                claimB: conflictItem.contradicts?.[0] || undefined,
              }
            } else {
              // Fallback: use current claim as source A, create placeholder for source B
              conflictData = {
                conflictId: `conflict-${idx}`,
                summary: triple.conflict_flags[0] || "Conflict detected between sources",
                sourceA: triple.source_pointer || {},
                sourceB: {}, // Placeholder - would need to fetch from contradicts
                claimA: `${triple.subject} ${triple.predicate} ${triple.object}`,
              }
            }
          }

          return {
            id: triple.claim_id || `claim-${idx}`,
            text: `${triple.subject} ${triple.predicate} ${triple.object}`,
            shortText: `${triple.subject} → ${triple.object}`,
            subject: triple.subject || "",
            predicate: triple.predicate || "",
            object: triple.object || "",
            confidence: triple.confidence,
            status,
            provenance,
            linkedRQ,
            sourcePointer: triple.source_pointer || {},
            evidence: triple.evidence || "",
            flags: triple.conflict_flags || [],
            citations: triple.citations || [],
            conflictData,
          }
        })

        setClaims(transformedClaims)
        setIsLoading(false)
      } catch (err) {
        console.error("Failed to fetch claims:", err)
        setError(err instanceof Error ? err.message : "Failed to load claims")
        setIsLoading(false)
      }
    }

    fetchClaims()
  }, [jobId, researchQuestions])

  // Filter claims
  const filteredClaims = useMemo(() => {
    let filtered = claims

    if (filterStatus) {
      filtered = filtered.filter((c) => c.status === filterStatus)
    }

    if (filterRQ) {
      filtered = filtered.filter((c) => c.linkedRQ === filterRQ)
    }

    return filtered
  }, [claims, filterStatus, filterRQ])

  // Status counts
  const statusCounts = useMemo(() => {
    const counts = {
      Proposed: 0,
      Flagged: 0,
      Accepted: 0,
      "Needs Review": 0,
    }
    claims.forEach((c) => {
      counts[c.status] = (counts[c.status] || 0) + 1
    })
    return counts
  }, [claims])

  if (error) {
    return (
      <Card className="p-4">
        <p className="text-sm text-destructive">{error}</p>
      </Card>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header with filters */}
      <div className="px-4 py-3 border-b border-border bg-muted/30 space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Knowledge Claims</h2>
          <span className="text-xs text-muted-foreground">{filteredClaims.length} of {claims.length}</span>
        </div>

        {/* Status filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setFilterStatus(null)}
            className={`text-xs px-2 py-1 rounded-md transition-colors ${
              filterStatus === null
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            All ({claims.length})
          </button>
          {Object.entries(statusCounts).map(([status, count]) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status as Claim["status"])}
              className={`text-xs px-2 py-1 rounded-md transition-colors ${
                filterStatus === status
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {status} ({count})
            </button>
          ))}
        </div>

        {/* RQ filter */}
        {researchQuestions.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground">RQ:</span>
            <button
              onClick={() => setFilterRQ(null)}
              className={`text-xs px-2 py-1 rounded-md transition-colors ${
                filterRQ === null
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              All
            </button>
            {researchQuestions.map((rq) => (
              <button
                key={rq}
                onClick={() => setFilterRQ(rq)}
                className={`text-xs px-2 py-1 rounded-md transition-colors truncate max-w-[120px] ${
                  filterRQ === rq
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
                title={rq}
              >
                {rq.substring(0, 20)}...
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Claims list */}
      <div className="flex-1 overflow-auto p-4 space-y-2">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : filteredClaims.length === 0 ? (
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">
              {claims.length === 0 ? "No claims available yet." : "No claims match the selected filters."}
            </p>
          </Card>
        ) : (
          filteredClaims.map((claim) => (
            <ClaimItem
              key={claim.id}
              claim={claim}
              onClick={() => setSelectedClaim(claim)}
            />
          ))
        )}
      </div>

      {/* Detail drawer */}
      {selectedClaim && (
        <ClaimDetailDrawer
          claim={selectedClaim}
          open={!!selectedClaim}
          onClose={() => setSelectedClaim(null)}
        />
      )}
    </div>
  )
}

