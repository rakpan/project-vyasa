//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Download, FileText, Table, Shield, Activity } from "lucide-react"
import { cn } from "@/lib/utils"
import { useProjectStore } from "@/state/useProjectStore"
import { toast } from "@/hooks/use-toast"

interface ManifestBarProps {
  manifest?: {
    metrics?: {
      total_words?: number
      total_claims?: number
      claims_per_100_words?: number
      citation_count?: number
    }
    totals?: {
      words?: number
      tables?: number
      citations?: number
      figures?: number
    }
    blocks?: Array<{
      tone_flags?: Array<unknown>
    }>
  }
  neutralityScore?: number
}

/**
 * Manifest Bar - Pinned to top of Manuscript editor
 * Displays real-time artifact metrics and provides manifest download
 */
export function ManifestBar({ manifest, neutralityScore = 100 }: ManifestBarProps) {
  const { activeJobId, activeProjectId } = useProjectStore()

  const wordCount = manifest?.metrics?.total_words ?? manifest?.totals?.words ?? 0
  const tableCount = manifest?.totals?.tables ?? 0
  const toneFlags = useMemo(() => {
    if (!manifest?.blocks) return 0
    return manifest.blocks.reduce((acc, block) => {
      return acc + (Array.isArray(block.tone_flags) ? block.tone_flags.length : 0)
    }, 0)
  }, [manifest?.blocks])
  const density = manifest?.metrics?.claims_per_100_words ?? 0
  const claims = manifest?.metrics?.total_claims ?? 0
  const citations = manifest?.metrics?.citation_count ?? manifest?.totals?.citations ?? 0

  const handleDownloadManifest = async () => {
    if (!activeJobId || !activeProjectId) {
      toast({
        title: "No active job",
        description: "Cannot download manifest without an active job.",
        variant: "destructive",
      })
      return
    }

    try {
      // Fetch manifest from orchestrator API
      const resp = await fetch(
        `/api/proxy/orchestrator/workflow/result/${activeJobId}?project_id=${encodeURIComponent(activeProjectId)}`
      )
      if (!resp.ok) {
        throw new Error(`Failed to fetch manifest: ${resp.status}`)
      }

      const data = await resp.json()
      const manifestData = data?.result?.artifact_manifest || data?.artifact_manifest

      if (!manifestData) {
        throw new Error("Manifest not found in job result")
      }

      // Create download blob
      const blob = new Blob([JSON.stringify(manifestData, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `artifact_manifest_${activeJobId}_${new Date().toISOString().split("T")[0]}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      toast({
        title: "Manifest downloaded",
        description: "Artifact manifest saved to your downloads.",
      })
    } catch (err: any) {
      toast({
        title: "Download failed",
        description: err?.message || "Could not download artifact manifest.",
        variant: "destructive",
      })
      console.error("Failed to download manifest:", err)
    }
  }

  const neutralityColor = useMemo(() => {
    if (neutralityScore >= 90) return "text-emerald-600"
    if (neutralityScore >= 70) return "text-amber-600"
    return "text-rose-600"
  }, [neutralityScore])

  const neutralityBadgeVariant = useMemo(() => {
    if (neutralityScore >= 90) return "default"
    if (neutralityScore >= 70) return "secondary"
    return "destructive"
  }, [neutralityScore])

  return (
    <div className="flex items-center justify-between gap-4 py-1.5 px-2 bg-slate-50/50 rounded-md border border-slate-200/50">
      {/* Metrics */}
      <div className="flex items-center gap-4 text-xs">
        {/* Word Count */}
        <div className="flex items-center gap-1.5">
          <FileText className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-medium text-foreground">{wordCount.toLocaleString()}</span>
          <span className="text-muted-foreground">words</span>
        </div>

        {/* Table Count */}
        <div className="flex items-center gap-1.5">
          <Table className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-medium text-foreground">{tableCount}</span>
          <span className="text-muted-foreground">tables</span>
        </div>

        {/* Neutrality Score */}
        <div className="flex items-center gap-1.5">
          <Shield className="h-3.5 w-3.5 text-muted-foreground" />
          <Badge variant={neutralityBadgeVariant} className="text-[10px] px-1.5 py-0 h-5">
            <span className={cn("font-medium", neutralityColor)}>
              {neutralityScore.toFixed(0)}% neutral
            </span>
          </Badge>
          {toneFlags > 0 && (
            <span className="text-muted-foreground text-[10px]">
              ({toneFlags} flag{toneFlags !== 1 ? "s" : ""})
            </span>
          )}
        </div>

        {/* Density / Claims */}
        <div className="flex items-center gap-1.5">
          <Activity className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-medium text-foreground">{claims}</span>
          <span className="text-muted-foreground">claims</span>
          <span className="text-muted-foreground">·</span>
          <span className="font-medium text-foreground">{density.toFixed(1)}</span>
          <span className="text-muted-foreground">per 100 words</span>
          <span className="text-muted-foreground">·</span>
          <span className="font-medium text-foreground">{citations}</span>
          <span className="text-muted-foreground">citations</span>
        </div>
      </div>

      {/* Download Button */}
      <Button
        size="sm"
        variant="outline"
        className="h-7 text-xs gap-1.5"
        onClick={handleDownloadManifest}
        disabled={!activeJobId || !manifest}
      >
        <Download className="h-3 w-3" />
        Download Manifest
      </Button>
    </div>
  )
}
