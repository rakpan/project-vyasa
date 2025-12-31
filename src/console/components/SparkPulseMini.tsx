"use client"

import { useEffect, useState } from "react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { createAbortableFetch, createIsMountedRef, startPolling } from "@/lib/async"

type Pulse = {
  memory_pressure: number
  unified_usage_gb: number
  active_cores: "performance" | "efficiency" | "hybrid" | "idle" | string
}

/**
 * Miniaturized Spark Pulse - thin sparkline in top corner with tooltip details.
 * Zen-First: Minimal visual footprint, details on demand.
 */
export function SparkPulseMini() {
  const [pulse, setPulse] = useState<Pulse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<number[]>([])

  useEffect(() => {
    // Track component mount status to prevent setState after unmount
    const mountedRef = createIsMountedRef()

    // Start polling with proper cleanup
    const pollingController = startPolling({
      intervalMs: 3000,
      immediate: true,
      fn: async (signal) => {
        try {
          // Use abortable fetch to ensure cancellation on unmount
          const { promise } = createAbortableFetch<Pulse>(
            "/system/pulse",
            { signal }
          )

          const json = await promise

          // Only update state if component is still mounted
          if (mountedRef.isMounted()) {
            setPulse(json)
            setError(null)
            // Update history for sparkline (keep last 20 points)
            setHistory((prev) => [...prev.slice(-19), json.memory_pressure])
          }
        } catch (err) {
          // Ignore AbortError (expected when stopping)
          if (err instanceof Error && err.name === "AbortError") {
            return
          }

          // Only update error state if component is still mounted
          if (mountedRef.isMounted()) {
            setError("No telemetry")
          }
        }
      },
      onError: (error) => {
        // Error handler only called for non-abort errors
        if (mountedRef.isMounted() && error.name !== "AbortError") {
          setError("No telemetry")
        }
      },
    })

    // Cleanup: mark as unmounted and stop polling
    return () => {
      mountedRef.unmount()
      pollingController.stop("Component unmounted")
    }
  }, [])

  const pressure = pulse?.memory_pressure ?? 0
  const usage = pulse?.unified_usage_gb ?? 0
  const cores = pulse?.active_cores || "idle"

  // Generate sparkline path
  const maxValue = 100
  const width = 60
  const height = 12
  const points = history.length > 1
    ? history.map((value, index) => {
        const x = (index / (history.length - 1)) * width
        const y = height - (value / maxValue) * height
        return `${index === 0 ? "M" : "L"} ${x} ${y}`
      }).join(" ")
    : ""

  const color = pressure < 70 ? "text-emerald-500" : pressure < 85 ? "text-amber-500" : "text-rose-600"
  const fillColor = pressure < 70 ? "fill-emerald-500/20" : pressure < 85 ? "fill-amber-500/20" : "fill-rose-600/20"

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-1.5 cursor-pointer">
            {error ? (
              <div className="w-[60px] h-[12px] bg-muted rounded" />
            ) : (
              <svg
                width={width}
                height={height}
                className={cn("overflow-visible", color)}
                viewBox={`0 0 ${width} ${height}`}
              >
                {points && (
                  <>
                    <path
                      d={`${points} L ${width} ${height} L 0 ${height} Z`}
                      className={fillColor}
                    />
                    <path
                      d={points}
                      stroke="currentColor"
                      strokeWidth="1.5"
                      fill="none"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </>
                )}
              </svg>
            )}
            <div className={cn("w-1.5 h-1.5 rounded-full", color.replace("text-", "bg-"))} />
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="text-xs">
          <div className="space-y-1">
            <div className="font-semibold">Spark Pulse</div>
            <div>Memory: {pressure.toFixed(1)}% ({usage.toFixed(1)} GB)</div>
            <div>Cores: {cores}</div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

