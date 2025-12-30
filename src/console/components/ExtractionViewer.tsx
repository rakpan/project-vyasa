"use client"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Triple } from "@/types/graph"

type EvidenceTriple = Triple & { evidence?: string }

type ExtractionViewerProps = {
  triples: EvidenceTriple[]
  title?: string
}

const CONFIDENCE_LABELS = [
  { threshold: 0.8, label: "High Confidence", className: "bg-emerald-600 text-white" },
  { threshold: 0.5, label: "Medium Confidence", className: "bg-amber-500 text-white" },
  { threshold: 0, label: "Low Confidence", className: "bg-rose-600 text-white" },
]

function confidenceBadge(confidence?: number) {
  if (confidence === undefined || confidence === null) {
    return <Badge variant="secondary">N/A</Badge>
  }
  const match = CONFIDENCE_LABELS.find((c) => confidence >= c.threshold) || CONFIDENCE_LABELS[2]
  return <Badge className={match.className}>{match.label}</Badge>
}

export function ExtractionViewer({ triples, title = "Extracted Claims" }: ExtractionViewerProps) {
  if (!triples || triples.length === 0) {
    return (
      <Card className="p-4">
        <p className="text-sm text-muted-foreground">No extracted claims available yet.</p>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">{title}</h3>
        <span className="text-xs text-muted-foreground">{triples.length} items</span>
      </div>
      <Separator />
      <div className="space-y-3">
        {triples.map((triple, idx) => (
          <Card key={`${triple.subject}-${triple.object}-${idx}`} className="p-4 space-y-2">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-semibold text-foreground">
                  {triple.subject} — {triple.predicate} → {triple.object}
                </p>
                <p className="text-xs text-muted-foreground">
                  Confidence: {triple.confidence !== undefined ? triple.confidence.toFixed(2) : "n/a"}
                </p>
              </div>
              {confidenceBadge(triple.confidence)}
            </div>
            <details className="rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-sm">
              <summary className="cursor-pointer font-medium">View evidence</summary>
              <p className="mt-2 text-muted-foreground">
                {triple.evidence && triple.evidence.trim().length > 0
                  ? triple.evidence
                  : "No evidence provided for this claim."}
              </p>
            </details>
          </Card>
        ))}
      </div>
    </div>
  )
}
