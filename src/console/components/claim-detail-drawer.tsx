"use client"

/**
 * Claim Detail Drawer Component
 * Shows full claim details with sources, citations, confidence, and flags
 */

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { FileText, AlertTriangle, CheckCircle2, Clock, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { ConflictCompareView } from "./conflict-compare-view"
import type { Claim } from "@/types/claim"

interface ClaimDetailDrawerProps {
  claim: Claim
  open: boolean
  onClose: () => void
}

const STATUS_ICONS: Record<Claim["status"], React.ComponentType<{ className?: string }>> = {
  Proposed: Clock,
  Flagged: AlertTriangle,
  Accepted: CheckCircle2,
  "Needs Review": AlertTriangle,
}

export function ClaimDetailDrawer({ claim, open, onClose }: ClaimDetailDrawerProps) {
  const StatusIcon = STATUS_ICONS[claim.status]
  const statusConfig = {
    Proposed: { label: "Proposed", color: "text-slate-600" },
    Flagged: { label: "Flagged", color: "text-red-600" },
    Accepted: { label: "Accepted", color: "text-emerald-600" },
    "Needs Review": { label: "Needs Review", color: "text-amber-600" },
  }[claim.status]

  // Build breadcrumb text
  const breadcrumbParts: string[] = []
  if (claim.provenance.proposed_by) {
    breadcrumbParts.push(`Proposed by: ${claim.provenance.proposed_by}`)
  }
  if (claim.provenance.verified_by) {
    breadcrumbParts.push(`Verified by: ${claim.provenance.verified_by}`)
  }
  if (claim.provenance.flagged_by) {
    breadcrumbParts.push(`Flagged by: ${claim.provenance.flagged_by}`)
  }
  const breadcrumbText = breadcrumbParts.join(" → ")

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <div className="flex items-center gap-2">
            <StatusIcon className={cn("h-5 w-5", statusConfig.color)} />
            <SheetTitle>Claim Details</SheetTitle>
          </div>
          <SheetDescription>
            Full provenance and evidence for this knowledge claim
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Status and Confidence */}
          <div className="flex items-center gap-3">
            <Badge variant="secondary" className="text-sm">
              {statusConfig.label}
            </Badge>
            {claim.confidence !== undefined && (
              <Badge
                variant={
                  claim.confidence >= 0.8 ? "default" : claim.confidence >= 0.5 ? "secondary" : "outline"
                }
                className="text-sm"
              >
                Confidence: {Math.round(claim.confidence * 100)}%
              </Badge>
            )}
            {claim.linkedRQ && (
              <Badge variant="outline" className="text-sm">
                RQ: {claim.linkedRQ}
              </Badge>
            )}
          </div>

          <Separator />

          {/* Full Claim Text */}
          <div>
            <h3 className="text-sm font-semibold text-foreground mb-2">Claim</h3>
            <div className="space-y-1">
              <p className="text-sm text-foreground">
                <span className="font-medium">{claim.subject}</span>{" "}
                <span className="text-muted-foreground">{claim.predicate}</span>{" "}
                <span className="font-medium">{claim.object}</span>
              </p>
              <p className="text-xs text-muted-foreground">{claim.text}</p>
            </div>
          </div>

          <Separator />

          {/* Provenance Breadcrumb */}
          <div>
            <h3 className="text-sm font-semibold text-foreground mb-2">Provenance</h3>
            <p className="text-sm text-muted-foreground flex items-center gap-1">
              <ChevronRight className="h-3 w-3" />
              {breadcrumbText || "No provenance available"}
            </p>
          </div>

          <Separator />

          {/* Sources/Citations */}
          <div>
            <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Sources
            </h3>
            {claim.sourcePointer.doc_hash || claim.sourcePointer.page ? (
              <div className="space-y-2">
                {claim.sourcePointer.doc_hash && (
                  <div className="text-xs text-muted-foreground">
                    <span className="font-medium">Document:</span> {claim.sourcePointer.doc_hash.substring(0, 16)}...
                  </div>
                )}
                {claim.sourcePointer.page && (
                  <div className="text-xs text-muted-foreground">
                    <span className="font-medium">Page:</span> {claim.sourcePointer.page}
                  </div>
                )}
                {claim.sourcePointer.snippet && (
                  <div className="p-2 rounded-md bg-muted/50 border border-border text-xs text-foreground">
                    {claim.sourcePointer.snippet}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No source information available</p>
            )}
          </div>

          {/* Citations */}
          {claim.citations.length > 0 && (
            <>
              <Separator />
              <div>
                <h3 className="text-sm font-semibold text-foreground mb-2">Citations</h3>
                <div className="flex flex-wrap gap-2">
                  {claim.citations.map((citation, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs">
                      {citation}
                    </Badge>
                  ))}
                </div>
              </div>
            </>
          )}

          <Separator />

          {/* Evidence */}
          {claim.evidence && (
            <div>
              <h3 className="text-sm font-semibold text-foreground mb-2">Evidence</h3>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">{claim.evidence}</p>
            </div>
          )}

          {/* Conflict Comparison View */}
          {claim.conflictData && (
            <>
              <Separator />
              <div>
                <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2 text-red-600">
                  <AlertTriangle className="h-4 w-4" />
                  Conflict Comparison
                </h3>
                <ConflictCompareView
                  sourceA={{
                    sourcePointer: claim.conflictData.sourceA,
                    claimText: claim.conflictData.claimA,
                    label: "Source A",
                  }}
                  sourceB={{
                    sourcePointer: claim.conflictData.sourceB,
                    claimText: claim.conflictData.claimB,
                    label: "Source B",
                  }}
                  conflictExplanation={claim.conflictData.summary}
                />
              </div>
            </>
          )}

          {/* Flags (fallback if no conflictData) */}
          {claim.flags.length > 0 && !claim.conflictData && (
            <>
              <Separator />
              <div>
                <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2 text-red-600">
                  <AlertTriangle className="h-4 w-4" />
                  Flags ({claim.flags.length})
                </h3>
                <div className="space-y-2">
                  {claim.flags.map((flag, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded-md bg-red-50 border border-red-200 text-xs text-red-700"
                    >
                      {flag}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

