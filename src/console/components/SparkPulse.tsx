"use client"

import { useEffect, useState } from "react"
import { Zap, Leaf, AlertTriangle } from "lucide-react"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

type Pulse = {
  memory_pressure: number
  unified_usage_gb: number
  active_cores: "performance" | "efficiency" | "hybrid" | "idle" | string
}

function gaugeClasses(pressure: number) {
  if (pressure < 70) return { bar: "bg-emerald-500", text: "text-emerald-600" }
  if (pressure < 85) return { bar: "bg-amber-500", text: "text-amber-600" }
  return { bar: "bg-rose-600", text: "text-rose-600" }
}

export function SparkPulse() {
  const [pulse, setPulse] = useState<Pulse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const fetchPulse = async () => {
      try {
        const res = await fetch("/system/pulse")
        if (!res.ok) throw new Error("Failed to fetch pulse")
        const json = (await res.json()) as Pulse
        if (mounted) {
          setPulse(json)
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          setError("No telemetry")
        }
      }
    }
    fetchPulse()
    const interval = setInterval(fetchPulse, 3000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  const pressure = pulse?.memory_pressure ?? 0
  const usage = pulse?.unified_usage_gb ?? 0
  const { bar, text } = gaugeClasses(pressure)

  const coreIcon =
    pulse?.active_cores === "performance" ? (
      <Zap className="h-4 w-4 animate-pulse text-emerald-500" />
    ) : pulse?.active_cores === "efficiency" ? (
      <Leaf className="h-4 w-4 animate-pulse text-sky-500" />
    ) : pulse?.active_cores === "hybrid" ? (
      <Zap className="h-4 w-4 animate-pulse text-amber-500" />
    ) : (
      <Leaf className="h-4 w-4 text-muted-foreground" />
    )

  return (
    <Card className="flex items-center gap-3 px-3 py-2">
      <div className="flex-1">
        <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
          <span>Spark Pulse</span>
          <span className={cn("font-semibold", text)}>{pressure.toFixed(1)}%</span>
        </div>
        <div className="h-2 w-full rounded bg-muted/60 overflow-hidden">
          <div className={cn("h-2", bar)} style={{ width: `${Math.min(pressure, 100)}%` }} />
        </div>
        <div className="mt-1 text-[11px] text-muted-foreground">
          {usage.toFixed(1)} GB unified • cores: {pulse?.active_cores || "idle"}
        </div>
      </div>
      <div>{error ? <AlertTriangle className="h-4 w-4 text-rose-500" /> : coreIcon}</div>
    </Card>
  )
}
