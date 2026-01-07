"use client"

import { useEffect, useRef, useState } from "react"
import { Brain, Calculator, Eye, AlertTriangle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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

const STATE_STYLES: Record<AgentState, string> = {
  idle: "bg-slate-50 text-slate-700 border-border/60",
  running: "bg-emerald-50 text-emerald-700 border-emerald-200/70",
  blocked: "bg-amber-50 text-amber-700 border-amber-200/70",
}

export function AgentHeartbeatPanel({ className }: { className?: string }) {
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
      setAgentStatuses(INITIAL_AGENTS.map((a) => ({ ...a, lastUpdate: Date.now(), state: "idle" as AgentState })))
      setConnectionStatus("disconnected")
      return
    }
    if (typeof window === "undefined") return

    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    const src = new EventSource(`/api/proxy/orchestrator/events/${activeJobId}`)
    eventSourceRef.current = src

    const checkHeartbeat = () => {
      const timeSinceLastHeartbeat = Date.now() - lastHeartbeat
      if (timeSinceLastHeartbeat > 60000) {
        setConnectionStatus("delayed")
      } else if (timeSinceLastHeartbeat > 30000) {
        setConnectionStatus("delayed")
      } else {
        setConnectionStatus("connected")
      }
    }

    src.onopen = () => {
      setConnectionStatus("connected")
      setLastHeartbeat(Date.now())
    }

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

        if (payload.type === "heartbeat") {
          setConnectionStatus("connected")
          return
        }

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
              if (agent.state === "running" && now - agent.lastUpdate > 5000) {
                return { ...agent, state: "idle" as AgentState, activity: "Idle", lastUpdate: now }
              }
              return agent
            })
          })
        }

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
    }

    heartbeatTimeoutRef.current = setInterval(checkHeartbeat, 10000)

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
    <Card className={cn("md:col-span-2 lg:col-span-2 bg-card/80 border-border/60", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-lg">Agents</CardTitle>
        {connectionStatus === "delayed" ? (
          <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-300">
            <AlertTriangle className="h-2.5 w-2.5 mr-1" />
            Status delayed
          </Badge>
        ) : (
          <Badge variant="outline" className="text-[10px] text-muted-foreground">
            {connectionStatus}
          </Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {manifestSummary && (manifestSummary.tables || manifestSummary.figures || manifestSummary.claims) ? (
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span>Claims: {manifestSummary.claims ?? 0}</span>
            <span>Tables: {manifestSummary.tables ?? 0}</span>
            <span>Figures: {manifestSummary.figures ?? 0}</span>
          </div>
        ) : null}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {agentStatuses.map((agent) => {
            const Icon = agent.icon
            return (
              <div key={agent.name} className={cn("flex items-center gap-3 rounded-lg border p-3", STATE_STYLES[agent.state])}>
                <div className="relative flex h-9 w-9 items-center justify-center rounded-md bg-white/70">
                  <Icon className="h-4 w-4" />
                  {(agent.state === "running" || agent.state === "blocked") && (
                    <span
                      className={cn(
                        "absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full",
                        agent.state === "blocked" ? "bg-amber-500" : agent.color,
                        "animate-pulse"
                      )}
                    />
                  )}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium">{agent.name}</div>
                  <div className="text-xs text-muted-foreground truncate">{agent.activity}</div>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
