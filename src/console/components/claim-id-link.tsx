"use client"

/**
 * ClaimIdLink Component
 * Clickable link for claim IDs that triggers evidence highlight
 */

import { Badge } from "@/components/ui/badge"
import { useAnchor } from "@/hooks/use-anchor"
import { cn } from "@/lib/utils"
import { ExternalLink } from "lucide-react"
import { useState, useEffect } from "react"
import type { SourceAnchor } from "@/hooks/use-anchor"

interface ClaimIdLinkProps {
  claimId: string
  sourcePointer?: {
    doc_hash?: string
    page?: number
    bbox?: [number, number, number, number]
    snippet?: string
  }
  sourceAnchor?: SourceAnchor
  className?: string
  variant?: "default" | "outline" | "secondary"
}

export function ClaimIdLink({
  claimId,
  sourcePointer,
  sourceAnchor,
  className,
  variant = "outline",
}: ClaimIdLinkProps) {
  const { activateClaim, scrollToAnchor } = useAnchor()
  const [anchor, setAnchor] = useState<SourceAnchor | null>(sourceAnchor || null)

  // Fetch anchor if not provided
  useEffect(() => {
    if (!anchor && !sourcePointer) {
      // Fetch from API
      fetch(`/api/proxy/orchestrator/api/claims/${claimId}/anchor`)
        .then((res) => res.json())
        .then((data) => {
          if (data.source_anchor) {
            setAnchor(data.source_anchor)
          }
        })
        .catch((err) => {
          console.warn(`Failed to fetch anchor for claim ${claimId}:`, err)
        })
    }
  }, [claimId, anchor, sourcePointer])

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    // Prefer source_anchor, fallback to sourcePointer, then fetch from API
    if (anchor) {
      scrollToAnchor(anchor)
    } else if (sourcePointer && sourcePointer.page && sourcePointer.bbox) {
      // Convert sourcePointer to anchor format
      const convertedAnchor: SourceAnchor = {
        doc_id: sourcePointer.doc_hash || "",
        page_number: sourcePointer.page,
        bbox: {
          x: sourcePointer.bbox[0],
          y: sourcePointer.bbox[1],
          w: sourcePointer.bbox[2] - sourcePointer.bbox[0],
          h: sourcePointer.bbox[3] - sourcePointer.bbox[1],
        },
        snippet: sourcePointer.snippet,
      }
      scrollToAnchor(convertedAnchor)
    } else {
      // Fetch anchor from API
      activateClaim(claimId)
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
      title={anchor || sourcePointer ? `View evidence on page ${anchor?.page_number || sourcePointer?.page}` : `Claim ${claimId}`}
    >
      {claimId}
      {(anchor || sourcePointer) && <ExternalLink className="h-3 w-3 ml-1" />}
    </Badge>
  )
}

