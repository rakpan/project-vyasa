//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useEffect, useRef, useState } from "react"
import { Brain, Calculator, Eye, AlertTriangle } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { useProjectStore } from "@/state/useProjectStore"

type AgentState = "idle" | "running" | "blocked"

interface AgentStatus {
  name: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  activity: string
  state: AgentState
  lastUpdate: number
}

const NODE_TO_AGENT: Record<string, { name: string; color: string }> = {
  vision: { name: "Vision", color: "bg-sky-500/70" },
  logician: { name: "Logician", color: "bg-amber-500/70" },
  brain: { name: "Brain", color: "bg-emerald-500/70" },
  "cortex-brain": { name: "Brain", color: "bg-emerald-500/70" },
}

const INITIAL_AGENTS: Omit<AgentStatus, "lastUpdate">[] = [
  { name: "Brain", icon: Brain, color: "bg-emerald-500/70", activity: "Idle", state: "idle" },
  { name: "Logician", icon: Calculator, color: "bg-amber-500/70", activity: "Idle", state: "idle" },
  { name: "Vision", icon: Eye, color: "bg-sky-500/70", activity: "Idle", state: "idle" },
]

/**
 * Agent Heartbeat Footer - Real-time status indicators for expert agents
 * Connected to LangGraph astream_events v2 stream
 * Shows idle/running/blocked states with backpressure resilience
 */
export function NavFooter() {
  const { activeJobId } = useProjectStore()
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>(
    INITIAL_AGENTS.map((a) => ({ ...a, lastUpdate: Date.now() }))
  )
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "delayed" | "disconnected">("connected")
  const [lastHeartbeat, setLastHeartbeat] = useState<number>(Date.now())
  const [manifestSummary, setManifestSummary] = useState<{ tables?: number; figures?: number; claims?: number }>({})

  const eventSourceRef = useRef<EventSource | null>(null)
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (!activeJobId) {
      // Reset to idle when no active job
      setAgentStatuses(INITIAL_AGENTS.map((a) => ({ ...a, lastUpdate: Date.now(), state: "idle" as AgentState })))
      setConnectionStatus("disconnected")
      return
    }
    if (typeof window === "undefined") return

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    const src = new EventSource(`/api/proxy/orchestrator/events/${activeJobId}`)
    eventSourceRef.current = src

    // Track heartbeat for backpressure detection
    const checkHeartbeat = () => {
      const timeSinceLastHeartbeat = Date.now() - lastHeartbeat
      if (timeSinceLastHeartbeat > 60000) {
        // No heartbeat for 60s = delayed
        setConnectionStatus("delayed")
      } else if (timeSinceLastHeartbeat > 30000) {
        // No heartbeat for 30s = warning
        setConnectionStatus("delayed")
      } else {
        setConnectionStatus("connected")
      }
    }

    src.onopen = () => {
      setConnectionStatus("connected")
      setLastHeartbeat(Date.now())
    }

    // Lightweight manifest summary fetch
    const fetchManifest = async () => {
      try {
        const resp = await fetch(`/api/proxy/orchestrator/workflow/result/${activeJobId}`)
        if (!resp.ok) return
        const data = await resp.json()
        const manifest = data?.result?.artifact_manifest || {}
        setManifestSummary({
          tables: manifest?.totals?.tables,
          figures: manifest?.totals?.figures,
          claims: manifest?.metrics?.total_claims,
        })
      } catch {
        // ignore
      }
    }
    fetchManifest()

    src.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data || "{}")
        const now = Date.now()
        setLastHeartbeat(now)

        // Handle heartbeat
        if (payload.type === "heartbeat") {
          setConnectionStatus("connected")
          return
        }

        // Handle node_start event (LangGraph astream_events v2)
        if (payload.type === "node_start" || (payload.type === "event" && payload.event === "on_node_start")) {
          const nodeName = (payload.node || payload.name || "").toLowerCase()
          const agentInfo = NODE_TO_AGENT[nodeName]
          if (!agentInfo) return

          setAgentStatuses((prev) => {
            return prev.map((agent) => {
              if (agent.name === agentInfo.name) {
                return {
                  ...agent,
                  state: "running" as AgentState,
                  activity: `Running ${agent.name}`,
                  lastUpdate: now,
                }
              }
              // Auto-transition other agents to idle after 5s of inactivity
              if (agent.state === "running" && now - agent.lastUpdate > 5000) {
                return { ...agent, state: "idle" as AgentState, activity: "Idle", lastUpdate: now }
              }
              return agent
            })
          })
        }

        // Handle node_end event
        if (payload.type === "node_end" || (payload.type === "event" && payload.event === "on_node_end")) {
          const nodeName = (payload.node || payload.name || "").toLowerCase()
          const agentInfo = NODE_TO_AGENT[nodeName]
          if (!agentInfo) return

          setAgentStatuses((prev) => {
            return prev.map((agent) => {
              if (agent.name === agentInfo.name) {
                return {
                  ...agent,
                  state: "idle" as AgentState,
                  activity: "Idle",
                  lastUpdate: now,
                }
              }
              return agent
            })
          })
        }

        // Handle interrupt/blocked state
        if (payload.type === "event" && payload.event === "on_interrupt") {
          setAgentStatuses((prev) => {
            return prev.map((agent) => ({
              ...agent,
              state: "blocked" as AgentState,
              activity: "Blocked (awaiting approval)",
              lastUpdate: now,
            }))
          })
        }
      } catch (err) {
        console.debug("Failed to parse event payload", err)
      }
    }

    src.onerror = () => {
      setConnectionStatus("disconnected")
      // Don't close on error - EventSource will auto-reconnect
    }

    // Periodic heartbeat check
    heartbeatTimeoutRef.current = setInterval(checkHeartbeat, 10000)

    // Auto-idle agents after 10s of no updates
    const idleCheckInterval = setInterval(() => {
      const now = Date.now()
      setAgentStatuses((prev) => {
        return prev.map((agent) => {
          if (agent.state === "running" && now - agent.lastUpdate > 10000) {
            return { ...agent, state: "idle" as AgentState, activity: "Idle", lastUpdate: now }
          }
          return agent
        })
      })
    }, 5000)

    const onVisibility = () => {
      if (document.hidden && src.readyState === EventSource.OPEN) {
        src.close()
      } else if (!document.hidden && src.readyState === EventSource.CLOSED) {
        // Reconnect when tab becomes visible
        src.close()
        const newSrc = new EventSource(`/api/proxy/orchestrator/events/${activeJobId}`)
        eventSourceRef.current = newSrc
      }
    }
    document.addEventListener("visibilitychange", onVisibility)

    return () => {
      document.removeEventListener("visibilitychange", onVisibility)
      if (heartbeatTimeoutRef.current) {
        clearInterval(heartbeatTimeoutRef.current)
      }
      clearInterval(idleCheckInterval)
      src.close()
      eventSourceRef.current = null
    }
  }, [activeJobId, lastHeartbeat])

  return (
    <div className="border-t border-slate-200 p-2 space-y-3">
      {/* Manifest summary */}
      {manifestSummary && (manifestSummary.tables || manifestSummary.figures || manifestSummary.claims) ? (
        <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1">
          <span>Manifest</span>
          <div className="flex items-center gap-3">
            <span>Claims: {manifestSummary.claims ?? 0}</span>
            <span>Tables: {manifestSummary.tables ?? 0}</span>
            <span>Figures: {manifestSummary.figures ?? 0}</span>
          </div>
        </div>
      ) : null}

      {/* Connection Status Badge */}
      {connectionStatus === "delayed" && (
        <div className="flex items-center justify-center">
          <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-300">
            <AlertTriangle className="h-2.5 w-2.5 mr-1" />
            Status delayed
          </Badge>
        </div>
      )}

      {/* Agent Status Indicators */}
      <div className="flex flex-col items-center gap-2">
        <TooltipProvider delayDuration={200}>
          {agentStatuses.map((agent) => {
            const Icon = agent.icon
            const isActive = agent.state === "running"
            const isBlocked = agent.state === "blocked"

            return (
              <Tooltip key={agent.name}>
                <TooltipTrigger asChild>
                  <div className="relative">
                    <div
                      className={cn(
                        "h-8 w-8 rounded-md flex items-center justify-center transition-colors",
                        isBlocked
                          ? "bg-amber-100 text-amber-700"
                          : isActive
                            ? "bg-slate-200 text-slate-700"
                            : "bg-slate-100 text-slate-600"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    {/* Pulsing status badge for active/blocked states */}
                    {(isActive || isBlocked) && (
                      <div
                        className={cn(
                          "absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full",
                          isBlocked ? "bg-amber-500" : agent.color,
                          "animate-pulse"
                        )}
                        style={{
                          animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                        }}
                      />
                    )}
                  </div>
                </TooltipTrigger>
                <TooltipContent side="right" className="text-xs">
                  <div className="space-y-1">
                    <div className="font-semibold">{agent.name}</div>
                    <div className="text-muted-foreground">{agent.activity}</div>
                    <div className="text-[10px] text-muted-foreground capitalize">{agent.state}</div>
                  </div>
                </TooltipContent>
              </Tooltip>
            )
          })}
        </TooltipProvider>
      </div>
    </div>
  )
}
