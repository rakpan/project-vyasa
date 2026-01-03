"use client"

/**
 * Rigor Impact Preview Component
 * Shows how rigor level affects human gates, tone, and precision
 */

import { CheckCircle2, AlertTriangle, Info } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface RigorImpactPreviewProps {
  rigorLevel: "exploratory" | "conservative"
}

export function RigorImpactPreview({ rigorLevel }: RigorImpactPreviewProps) {
  const isConservative = rigorLevel === "conservative"

  const humanGates = {
    exploratory: {
      level: "Minimal",
      description: "Fewer human review checkpoints. Faster iteration.",
      icon: CheckCircle2,
      color: "text-blue-600",
    },
    conservative: {
      level: "Enforced",
      description: "More human review checkpoints. Higher quality assurance.",
      icon: AlertTriangle,
      color: "text-amber-600",
    },
  }

  const tone = {
    exploratory: {
      level: "Warn",
      description: "Tone violations flagged but not blocking. Allows casual language.",
      icon: Info,
      color: "text-blue-600",
    },
    conservative: {
      level: "Strict",
      description: "Tone violations are blocking. Enforces neutral, academic language.",
      icon: AlertTriangle,
      color: "text-red-600",
    },
  }

  const precision = {
    exploratory: {
      level: "Relaxed",
      description: "Allows more decimal places. Flexible precision rules.",
      icon: CheckCircle2,
      color: "text-blue-600",
    },
    conservative: {
      level: "Strict",
      description: "Limited to 2 decimal places. Enforces precision contracts.",
      icon: AlertTriangle,
      color: "text-amber-600",
    },
  }

  const currentHumanGates = humanGates[rigorLevel]
  const currentTone = tone[rigorLevel]
  const currentPrecision = precision[rigorLevel]

  const HumanGatesIcon = currentHumanGates.icon
  const ToneIcon = currentTone.icon
  const PrecisionIcon = currentPrecision.icon

  return (
    <Card className="border-primary/20">
      <CardHeader>
        <CardTitle className="text-base">Rigor Impact Preview</CardTitle>
        <p className="text-sm text-muted-foreground">
          How {rigorLevel} rigor affects your project workflow
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Human Gates */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HumanGatesIcon className={cn("h-4 w-4", currentHumanGates.color)} />
              <span className="text-sm font-medium">Human Gates</span>
            </div>
            <Badge
              variant={isConservative ? "default" : "secondary"}
              className={cn(
                "text-xs",
                isConservative && "bg-amber-100 text-amber-800 border-amber-300"
              )}
            >
              {currentHumanGates.level}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground pl-6">{currentHumanGates.description}</p>
        </div>

        {/* Tone */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ToneIcon className={cn("h-4 w-4", currentTone.color)} />
              <span className="text-sm font-medium">Tone Enforcement</span>
            </div>
            <Badge
              variant={isConservative ? "destructive" : "secondary"}
              className="text-xs"
            >
              {currentTone.level}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground pl-6">{currentTone.description}</p>
        </div>

        {/* Precision */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PrecisionIcon className={cn("h-4 w-4", currentPrecision.color)} />
              <span className="text-sm font-medium">Precision Rules</span>
            </div>
            <Badge
              variant={isConservative ? "default" : "secondary"}
              className={cn(
                "text-xs",
                isConservative && "bg-amber-100 text-amber-800 border-amber-300"
              )}
            >
              {currentPrecision.level}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground pl-6">{currentPrecision.description}</p>
        </div>

        {/* Additional Info */}
        <div className="pt-2 border-t text-xs text-muted-foreground">
          <p>
            <strong>Note:</strong> This preview is informational only. Rigor level can be changed
            later, but it affects all new artifacts created for this project.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

