// SPDX-License-IdentifierText: 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
"use client"

import { useMemo, useState } from "react"
import { ShieldCheck, AlertTriangle, RefreshCw } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { useProjectStore } from "@/state/useProjectStore"
import { toast } from "@/hooks/use-toast"

type Manifest = {
  metrics?: {
    total_words?: number
    total_claims?: number
    claims_per_100_words?: number
    citation_count?: number
  }
  totals?: {
    tables?: number
    figures?: number
  }
  flags?: string[]
}

interface ManuscriptHealthProps {
  manifest?: Manifest | null
  onRefresh?: () => void
}

export function ManuscriptHealthTile({ manifest, onRefresh }: ManuscriptHealthProps) {
  const { activeProject, updateRigor } = useProjectStore()
  const [updating, setUpdating] = useState(false)

  const metrics = manifest?.metrics || {}
  const totals = manifest?.totals || {}
  const flags = manifest?.flags || []

  const severity = useMemo(() => {
    if (flags.length > 0) return "warn"
    return "ok"
  }, [flags])

  const handleRigorToggle = async (checked: boolean) => {
    if (!activeProject?.id) return
    const next = checked ? "conservative" : "exploratory"
    setUpdating(true)
    try {
      await updateRigor(next)
      toast({ title: "Rigor updated", description: `Rigor set to ${next}.` })
    } catch (err: any) {
      toast({ title: "Update failed", description: err?.message || "Unable to update rigor", variant: "destructive" })
    } finally {
      setUpdating(false)
    }
  }

  return (
    <Card className="bg-white border border-slate-200">
      <CardHeader className="pb-2 flex items-center justify-between space-y-0">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-slate-900" />
          Manuscript Health
        </CardTitle>
        <div className="flex items-center gap-2 text-xs">
          <Label htmlFor="rigor-toggle" className="text-muted-foreground">
            Rigor
          </Label>
          <Badge variant="outline" className="text-[10px]">
            {activeProject?.rigor_level || "exploratory"}
          </Badge>
          <Switch
            id="rigor-toggle"
            checked={(activeProject?.rigor_level || "exploratory") === "conservative"}
            onCheckedChange={handleRigorToggle}
            disabled={!activeProject?.id || updating}
          />
        </div>
      </CardHeader>
      <CardContent className="flex items-center justify-between text-sm">
        <div className="grid grid-cols-3 gap-4">
          <Metric label="Words" value={metrics.total_words ?? 0} />
          <Metric label="Claims" value={metrics.total_claims ?? 0} />
          <Metric label="Density" value={(metrics.claims_per_100_words ?? 0).toFixed(1)} suffix="per 100w" />
          <Metric label="Citations" value={metrics.citation_count ?? 0} />
          <Metric label="Tables" value={totals.tables ?? 0} />
          <Metric label="Figures" value={totals.figures ?? 0} />
        </div>
        <div className="flex flex-col items-end gap-2">
          <Badge variant={severity === "ok" ? "default" : "destructive"} className="text-[10px]">
            {severity === "ok" ? "Healthy" : `${flags.length} flag${flags.length === 1 ? "" : "s"}`}
          </Badge>
          {severity !== "ok" && (
            <div className="flex items-center gap-1 text-xs text-amber-600">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>Review tone/binding/precision</span>
            </div>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-xs gap-1"
            onClick={onRefresh}
            disabled={!onRefresh}
          >
            <RefreshCw className="h-3 w-3" />
            Refresh
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function Metric({ label, value, suffix }: { label: string; value: number | string; suffix?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="text-sm font-semibold text-slate-900">
        {value}
        {suffix ? <span className="text-[11px] text-muted-foreground ml-1">{suffix}</span> : null}
      </span>
    </div>
  )
}
