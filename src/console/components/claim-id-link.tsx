"use client"

/**
 * ClaimIdLink Component
 * Clickable link for claim IDs that triggers evidence highlight
 */

import { Badge } from "@/components/ui/badge"
import { useEvidence } from "@/contexts/evidence-context"
import { cn } from "@/lib/utils"
import { ExternalLink } from "lucide-react"

interface ClaimIdLinkProps {
  claimId: string
  sourcePointer?: {
    doc_hash?: string
    page?: number
    bbox?: [number, number, number, number]
    snippet?: string
  }
  className?: string
  variant?: "default" | "outline" | "secondary"
}

export function ClaimIdLink({
  claimId,
  sourcePointer,
  className,
  variant = "outline",
}: ClaimIdLinkProps) {
  const { setHighlight } = useEvidence()

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (sourcePointer && sourcePointer.page && sourcePointer.bbox) {
      // Convert bbox to EvidenceCoordinates format
      const coords = {
        page: sourcePointer.page,
        bbox: {
          x1: sourcePointer.bbox[0],
          y1: sourcePointer.bbox[1],
          x2: sourcePointer.bbox[2],
          y2: sourcePointer.bbox[3],
        },
        doc_hash: sourcePointer.doc_hash,
        snippet: sourcePointer.snippet,
        claim_id: claimId,
      }
      setHighlight(coords)
    } else {
      // Fallback: try to fetch claim data
      // This could be enhanced to fetch from API
      console.warn(`No source pointer available for claim ${claimId}`)
    }
  }

  return (
    <Badge
      variant={variant}
      className={cn(
        "cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors text-xs",
        className
      )}
      onClick={handleClick}
      title={sourcePointer ? `View evidence on page ${sourcePointer.page}` : `Claim ${claimId}`}
    >
      {claimId}
      {sourcePointer && <ExternalLink className="h-3 w-3 ml-1" />}
    </Badge>
  )
}

