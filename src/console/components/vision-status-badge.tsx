"use client"

/**
 * Vision Status Badge Component
 * Displays vision service status (OFF/ON/Healthy/Down) based on orchestrator health endpoint
 */

import { useState, useEffect } from "react"
import { Eye, EyeOff, AlertCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface VisionStatus {
  enabled: boolean
  healthy: boolean
  reason?: string
}

export function VisionStatusBadge() {
  const [status, setStatus] = useState<VisionStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchVisionStatus = async () => {
      try {
        const response = await fetch("/api/proxy/orchestrator/health?deep=true", {
          method: "GET",
          cache: "no-store",
        })

        if (!response.ok) {
          setStatus({ enabled: false, healthy: false, reason: "Health check failed" })
          setIsLoading(false)
          return
        }

        const data = await response.json()
        const visionStatus = data.dependencies?.vision

        if (visionStatus) {
          setStatus({
            enabled: visionStatus.enabled ?? false,
            healthy: visionStatus.healthy ?? false,
            reason: visionStatus.reason,
          })
        } else {
          // Fallback if vision status not in response
          setStatus({ enabled: false, healthy: false, reason: "Status unknown" })
        }
      } catch (error) {
        setStatus({ enabled: false, healthy: false, reason: "Failed to fetch status" })
      } finally {
        setIsLoading(false)
      }
    }

    fetchVisionStatus()
    // Poll every 30 seconds
    const interval = setInterval(fetchVisionStatus, 30000)

    return () => clearInterval(interval)
  }, [])

  if (isLoading) {
    return (
      <Badge variant="outline" className="text-xs">
        Vision: Loading...
      </Badge>
    )
  }

  if (!status) {
    return null
  }

  const getBadgeContent = () => {
    if (!status.enabled) {
      return (
        <>
          <EyeOff className="h-3 w-3 mr-1" />
          Vision: OFF
        </>
      )
    }

    if (status.healthy) {
      return (
        <>
          <Eye className="h-3 w-3 mr-1 text-emerald-600" />
          Vision: ON (Healthy)
        </>
      )
    }

    return (
      <>
        <AlertCircle className="h-3 w-3 mr-1 text-amber-600" />
        Vision: ON (Down)
      </>
    )
  }

  const getVariant = () => {
    if (!status.enabled) {
      return "outline"
    }
    if (status.healthy) {
      return "default"
    }
    return "destructive"
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant={getVariant()} className="text-xs cursor-help">
            {getBadgeContent()}
          </Badge>
        </TooltipTrigger>
        {status.reason && (
          <TooltipContent>
            <p className="text-xs">{status.reason}</p>
          </TooltipContent>
        )}
      </Tooltip>
    </TooltipProvider>
  )
}
