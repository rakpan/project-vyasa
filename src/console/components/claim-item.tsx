"use client"

/**
 * Claim Item Component
 * Displays a single claim with breadcrumbs, status, and RQ link
 */

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { ChevronRight, HelpCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Claim } from "@/types/claim"
import { useAnchor } from "@/hooks/use-anchor"

interface ClaimItemProps {
  claim: Claim
  onClick: () => void
}

const STATUS_CONFIG: Record<Claim["status"], { label: string; color: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  Proposed: {
    label: "Proposed",
    color: "bg-slate-500",
    variant: "secondary",
  },
  Flagged: {
    label: "Flagged",
    color: "bg-red-500",
    variant: "destructive",
  },
  Accepted: {
    label: "Accepted",
    color: "bg-emerald-500",
    variant: "default",
  },
  "Needs Review": {
    label: "Needs Review",
    color: "bg-amber-500",
    variant: "outline",
  },
}

export function ClaimItem({ claim, onClick }: ClaimItemProps) {
  const statusConfig = STATUS_CONFIG[claim.status]
  const { scrollToAnchor } = useAnchor()

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

  // Handle click: scroll to anchor if available, then call onClick
  const handleClick = () => {
    // If claim has source_anchor, scroll to it
    if (claim.source_anchor) {
      scrollToAnchor(claim.source_anchor)
    }
    // Call original onClick handler
    onClick()
  }

  // Confidence badge
  const confidenceBadge = claim.confidence !== undefined ? (
    <Badge
      variant={
        claim.confidence >= 0.8 ? "default" : claim.confidence >= 0.5 ? "secondary" : "outline"
      }
      className="text-xs"
    >
      {Math.round(claim.confidence * 100)}%
    </Badge>
  ) : null

  return (
    <Card
      className={cn(
        "p-3 cursor-pointer transition-all hover:shadow-md hover:border-primary/50",
        claim.status === "Flagged" && "border-red-300 bg-red-50/30",
        claim.status === "Accepted" && "border-emerald-300 bg-emerald-50/30"
      )}
      onClick={handleClick}
    >
      <div className="space-y-2">
        {/* Header: Status and Confidence */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Badge variant={statusConfig.variant} className="text-xs flex-shrink-0">
              {statusConfig.label}
            </Badge>
            {claim.linkedRQ && (
              <Badge variant="outline" className="text-xs truncate max-w-[200px]" title={claim.linkedRQ}>
                RQ: {claim.linkedRQ.substring(0, 30)}...
              </Badge>
            )}
          </div>
          {confidenceBadge}
        </div>

        {/* Claim text */}
        <p className="text-sm font-medium text-foreground line-clamp-2">
          {claim.shortText}
        </p>

        {/* Breadcrumb line */}
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <ChevronRight className="h-3 w-3" />
          <span className="truncate">{breadcrumbText || "No provenance available"}</span>
        </div>

        {/* Flags indicator with Why tooltip */}
        {claim.flags.length > 0 && (
          <div className="flex items-center gap-1">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-1">
                    <Badge variant="destructive" className="text-xs">
                      {claim.flags.length} flag{claim.flags.length > 1 ? "s" : ""}
                    </Badge>
                    {claim.conflictData && (
                      <HelpCircle className="h-3 w-3 text-muted-foreground cursor-help" />
                    )}
                  </div>
                </TooltipTrigger>
                {claim.conflictData && (
                  <TooltipContent side="right" className="max-w-xs">
                    <p className="text-xs">
                      {claim.conflictData.summary || "Source A asserts this claim, while Source B contradicts it."}
                    </p>
                  </TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          </div>
        )}
      </div>
    </Card>
  )
}

