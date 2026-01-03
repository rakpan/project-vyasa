"use client"

/**
 * Conflict Compare View Component
 * Side-by-side source comparison for conflicted claims
 * Shows Source A and Source B excerpts with page references
 */

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { FileText, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { SourcePointer } from "@/types/claim"

interface ConflictSource {
  sourcePointer: SourcePointer
  claimText?: string
  label?: string
}

interface ConflictCompareViewProps {
  sourceA: ConflictSource
  sourceB: ConflictSource
  conflictExplanation?: string
  className?: string
}

export function ConflictCompareView({
  sourceA,
  sourceB,
  conflictExplanation,
  className,
}: ConflictCompareViewProps) {
  const formatPageRef = (pointer: SourcePointer) => {
    if (pointer.page) {
      return `Page ${pointer.page}`
    }
    if (pointer.doc_hash) {
      return `Doc: ${pointer.doc_hash.substring(0, 8)}...`
    }
    return "Unknown source"
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Conflict explanation header */}
      {conflictExplanation && (
        <Card className="p-3 bg-amber-50 border-amber-200">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-900">Conflict Detected</p>
              <p className="text-xs text-amber-700 mt-1">{conflictExplanation}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Side-by-side comparison */}
      <div className="grid grid-cols-2 gap-4">
        {/* Source A */}
        <Card className="p-4 border-l-4 border-l-blue-500">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-600" />
                <h3 className="text-sm font-semibold text-foreground">
                  {sourceA.label || "Source A"}
                </h3>
              </div>
              <Badge variant="outline" className="text-xs">
                {formatPageRef(sourceA.sourcePointer)}
              </Badge>
            </div>

            {sourceA.claimText && (
              <div className="p-2 rounded-md bg-blue-50 border border-blue-200">
                <p className="text-xs font-medium text-blue-900 mb-1">Claim:</p>
                <p className="text-xs text-blue-800">{sourceA.claimText}</p>
              </div>
            )}

            {sourceA.sourcePointer.snippet && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Excerpt:</p>
                <div className="p-3 rounded-md bg-muted/50 border border-border text-sm text-foreground whitespace-pre-wrap">
                  {sourceA.sourcePointer.snippet}
                </div>
              </div>
            )}

            {!sourceA.sourcePointer.snippet && (
              <p className="text-xs text-muted-foreground italic">No excerpt available</p>
            )}

            {/* Source metadata */}
            <div className="pt-2 border-t border-border space-y-1">
              {sourceA.sourcePointer.doc_hash && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium">Document:</span> {sourceA.sourcePointer.doc_hash.substring(0, 16)}...
                </p>
              )}
              {sourceA.sourcePointer.bbox && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium">Location:</span> BBox {sourceA.sourcePointer.bbox.join(", ")}
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* Source B */}
        <Card className="p-4 border-l-4 border-l-red-500">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-red-600" />
                <h3 className="text-sm font-semibold text-foreground">
                  {sourceB.label || "Source B"}
                </h3>
              </div>
              <Badge variant="outline" className="text-xs">
                {formatPageRef(sourceB.sourcePointer)}
              </Badge>
            </div>

            {sourceB.claimText && (
              <div className="p-2 rounded-md bg-red-50 border border-red-200">
                <p className="text-xs font-medium text-red-900 mb-1">Claim:</p>
                <p className="text-xs text-red-800">{sourceB.claimText}</p>
              </div>
            )}

            {sourceB.sourcePointer.snippet && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Excerpt:</p>
                <div className="p-3 rounded-md bg-muted/50 border border-border text-sm text-foreground whitespace-pre-wrap">
                  {sourceB.sourcePointer.snippet}
                </div>
              </div>
            )}

            {!sourceB.sourcePointer.snippet && (
              <p className="text-xs text-muted-foreground italic">No excerpt available</p>
            )}

            {/* Source metadata */}
            <div className="pt-2 border-t border-border space-y-1">
              {sourceB.sourcePointer.doc_hash && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium">Document:</span> {sourceB.sourcePointer.doc_hash.substring(0, 16)}...
                </p>
              )}
              {sourceB.sourcePointer.bbox && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium">Location:</span> BBox {sourceB.sourcePointer.bbox.join(", ")}
                </p>
              )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

