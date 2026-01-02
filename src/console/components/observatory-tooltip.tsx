//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useEffect, useState, useMemo } from "react"
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTooltip } from "recharts"

interface ObservatoryData {
  hardware?: {
    series?: {
      uma_utilization_pct?: Array<{ timestamp: string; value: number }>
    }
  }
}

/**
 * Observatory Tooltip Content - Shows mini VRAM usage sparkline
 * Fetches latest observatory data for DGX Spark hardware metrics
 */
export function ObservatoryTooltipContent() {
  const [data, setData] = useState<ObservatoryData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Use the same endpoint as the observatory page (proxied via Next.js API route)
        const res = await fetch("/api/system/observatory", { cache: "no-store" })
        if (res.ok) {
          const json = await res.json()
          setData(json)
        }
      } catch (err) {
        console.debug("Failed to fetch observatory data for tooltip:", err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const sparklineData = useMemo(() => {
    const series = data?.hardware?.series?.uma_utilization_pct || []
    // Take last 20 points for mini sparkline
    return series.slice(-20).map((p) => ({ t: p.timestamp, v: p.value }))
  }, [data])

  const currentValue = useMemo(() => {
    const series = data?.hardware?.series?.uma_utilization_pct || []
    return series.length > 0 ? series[series.length - 1]?.value : null
  }, [data])

  if (loading) {
    return (
      <div className="p-2 text-xs">
        <div className="font-semibold mb-1">Observatory</div>
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-2 space-y-2 min-w-[200px]">
      <div className="flex items-center justify-between">
        <div className="font-semibold text-xs">DGX Spark VRAM</div>
        {currentValue !== null && (
          <div className="text-xs font-medium text-primary">
            {currentValue.toFixed(1)}%
          </div>
        )}
      </div>
      {sparklineData.length > 0 ? (
        <div className="h-16 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparklineData}>
              <defs>
                <linearGradient id="vram-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" hide />
              <YAxis hide domain={[0, 128]} />
              <RechartsTooltip
                contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: "10px" }}
                labelFormatter={() => ""}
                formatter={(value: number) => [`${value.toFixed(1)}%`, "UMA"]}
              />
              <Area
                type="monotone"
                dataKey="v"
                stroke="hsl(var(--primary))"
                fill="url(#vram-gradient)"
                strokeWidth={1.5}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">No data available</div>
      )}
      <div className="text-[10px] text-muted-foreground pt-1 border-t border-border/50">
        Unified Memory (UMA) utilization trend
      </div>
    </div>
  )
}

