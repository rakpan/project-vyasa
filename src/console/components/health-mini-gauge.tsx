"use client"

/**
 * Health Mini Gauge Component
 * Displays a compact health indicator with tooltip showing detailed metrics
 */

import { useMemo } from "react"
import { Activity, AlertTriangle, CheckCircle2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import type { ManifestSummary } from "@/types/project"

interface HealthMiniGaugeProps {
  manifest?: ManifestSummary
  openFlagsCount?: number
  status?: "Idle" | "Processing" | "AttentionNeeded"
  className?: string
}

export function HealthMiniGauge({
  manifest,
  openFlagsCount = 0,
  status,
  className,
}: HealthMiniGaugeProps) {
  const healthScore = useMemo(() => {
    if (!manifest) return null

    // Ensure manifest has required fields (defensive)
    const flags_count_by_type = manifest.flags_count_by_type || {}
    const density = manifest.density ?? 0
    const openFlagsCount_safe = openFlagsCount ?? 0

    // Base score from flags
    const totalFlags = Object.values(flags_count_by_type).reduce(
      (sum, count) => sum + (typeof count === "number" ? count : 0),
      0
    )
    const flagsPenalty = Math.min(totalFlags * 5, 50) // Max 50 point penalty
    const openFlagsPenalty = Math.min(openFlagsCount_safe * 10, 30) // Max 30 point penalty

    // Base score: 100 - penalties
    let score = 100 - flagsPenalty - openFlagsPenalty

    // Bonus for good density (2-5 claims per 100 words is ideal)
    if (density >= 2 && density <= 5) {
      score += 5
    }

    // Penalty for very low density
    if (density < 1) {
      score -= 10
    }

    return Math.max(0, Math.min(100, score))
  }, [manifest, openFlagsCount])

  const healthLevel = useMemo(() => {
    if (healthScore === null) return "unknown"
    if (healthScore >= 80) return "excellent"
    if (healthScore >= 60) return "good"
    if (healthScore >= 40) return "fair"
    return "poor"
  }, [healthScore])

  const healthColor = {
    excellent: "text-emerald-600",
    good: "text-blue-600",
    fair: "text-amber-600",
    poor: "text-red-600",
    unknown: "text-muted-foreground",
  }[healthLevel]

  const healthBg = {
    excellent: "bg-emerald-50 border-emerald-200",
    good: "bg-blue-50 border-blue-200",
    fair: "bg-amber-50 border-amber-200",
    poor: "bg-red-50 border-red-200",
    unknown: "bg-muted border-border",
  }[healthLevel]

  const tooltipContent = manifest ? (
    <div className="space-y-2 text-sm">
      <div className="font-semibold">Manuscript Health</div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-muted-foreground">Words:</span>{" "}
          {manifest.words.toLocaleString()}
        </div>
        <div>
          <span className="text-muted-foreground">Claims:</span>{" "}
          {manifest.claims.toLocaleString()}
        </div>
        <div>
          <span className="text-muted-foreground">Density:</span>{" "}
          {manifest.density.toFixed(1)}/100
        </div>
        <div>
          <span className="text-muted-foreground">Citations:</span>{" "}
          {manifest.citations}
        </div>
        <div>
          <span className="text-muted-foreground">Tables:</span> {manifest.tables}
        </div>
        <div>
          <span className="text-muted-foreground">Figures:</span>{" "}
          {manifest.figures}
        </div>
      </div>
      {Object.keys(manifest.flags_count_by_type || {}).length > 0 && (
        <div className="pt-2 border-t">
          <div className="text-xs font-medium mb-1">Flags:</div>
          <div className="space-y-1">
            {Object.entries(manifest.flags_count_by_type).map(([type, count]) => (
              <div key={type} className="text-xs">
                {type}: {count}
              </div>
            ))}
          </div>
        </div>
      )}
      {openFlagsCount > 0 && (
        <div className="pt-2 border-t text-xs text-amber-600">
          Open flags: {openFlagsCount}
        </div>
      )}
      {healthScore !== null && (
        <div className="pt-2 border-t text-xs font-medium">
          Health Score: {healthScore.toFixed(0)}/100
        </div>
      )}
    </div>
  ) : (
    <div className="text-sm text-muted-foreground">No manifest data available</div>
  )

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs font-medium cursor-help",
              healthBg,
              healthColor,
              className
            )}
          >
            {status === "Processing" ? (
              <Activity className="h-3 w-3 animate-pulse" />
            ) : status === "AttentionNeeded" ? (
              <AlertTriangle className="h-3 w-3" />
            ) : healthScore !== null && healthScore >= 80 ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <Activity className="h-3 w-3" />
            )}
            <span>
              {healthScore !== null
                ? `${healthScore.toFixed(0)}%`
                : status === "Processing"
                  ? "Processing"
                  : status === "AttentionNeeded"
                    ? "Needs Attention"
                    : "N/A"}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          {tooltipContent}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

