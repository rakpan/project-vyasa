"use client"

/**
 * Opik Live Feed Panel
 * Collapsible bottom panel showing live node execution logs for power users
 */

import { useState, useEffect, useRef } from "react"
import { ChevronUp, ChevronDown, ExternalLink, Clock, CheckCircle2, XCircle, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { cn } from "@/lib/utils"
import Link from "next/link"

type NodeExecutionEvent = {
  node_name: string
  duration_ms: number
  status: "success" | "error" | "pending"
  timestamp: string
  job_id?: string
  project_id?: string
  metadata?: Record<string, any>
}

interface OpikLiveFeedPanelProps {
  jobId?: string
  opikEnabled?: boolean
  opikTraceUrl?: string
}

export function OpikLiveFeedPanel({ jobId, opikEnabled, opikTraceUrl }: OpikLiveFeedPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [events, setEvents] = useState<NodeExecutionEvent[]>([])
  const [selectedEvent, setSelectedEvent] = useState<NodeExecutionEvent | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Fetch node execution events
  useEffect(() => {
    if (!isExpanded || !opikEnabled || !jobId) {
      setEvents([])
      return
    }

    let intervalId: NodeJS.Timeout
    let eventSource: EventSource | null = null

    const fetchEvents = async () => {
      try {
        setIsLoading(true)
        // Try to fetch from orchestrator telemetry endpoint
        const response = await fetch(`/api/proxy/orchestrator/jobs/${jobId}/events`, {
          cache: "no-store",
        })
        
        if (response.ok) {
          const data = await response.json()
          if (Array.isArray(data.events)) {
            setEvents((prev) => {
              // Merge new events, avoiding duplicates
              const existingIds = new Set(prev.map((e) => `${e.node_name}-${e.timestamp}`))
              const newEvents = data.events.filter(
                (e: NodeExecutionEvent) => !existingIds.has(`${e.node_name}-${e.timestamp}`)
              )
              return [...prev, ...newEvents].slice(-100) // Keep last 100 events
            })
          }
        }
      } catch (err) {
        console.error("Failed to fetch Opik events:", err)
      } finally {
        setIsLoading(false)
      }
    }

    // Initial fetch
    fetchEvents()

    // Poll every 2 seconds
    intervalId = setInterval(fetchEvents, 2000)

    // Try SSE if available
    try {
      eventSource = new EventSource(`/api/proxy/orchestrator/jobs/${jobId}/stream`)
      eventSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === "node_execution") {
            const event: NodeExecutionEvent = {
              node_name: data.node_name || "unknown",
              duration_ms: data.duration_ms || 0,
              status: data.status || "success",
              timestamp: data.timestamp || new Date().toISOString(),
              job_id: data.job_id,
              project_id: data.project_id,
              metadata: data.metadata,
            }
            setEvents((prev) => {
              const existingIds = new Set(prev.map((e) => `${e.node_name}-${e.timestamp}`))
              if (!existingIds.has(`${event.node_name}-${event.timestamp}`)) {
                return [...prev, event].slice(-100)
              }
              return prev
            })
          }
        } catch (err) {
          console.error("Failed to parse SSE event:", err)
        }
      }
      eventSource.onerror = () => {
        // SSE failed, fall back to polling
        if (eventSource) {
          eventSource.close()
          eventSource = null
        }
      }
    } catch (err) {
      // SSE not available, use polling only
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId)
      }
      if (eventSource) {
        eventSource.close()
      }
    }
  }, [isExpanded, opikEnabled, jobId])

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (scrollRef.current && isExpanded) {
      // ScrollArea wraps content, so we need to find the scrollable element
      const scrollable = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollable) {
        scrollable.scrollTop = scrollable.scrollHeight
      }
    }
  }, [events, isExpanded])

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString()
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle2 className="h-3 w-3 text-green-500" />
      case "error":
        return <XCircle className="h-3 w-3 text-red-500" />
      case "pending":
        return <AlertCircle className="h-3 w-3 text-yellow-500" />
      default:
        return <Clock className="h-3 w-3 text-muted-foreground" />
    }
  }

  if (!opikEnabled) {
    return (
      <div className="border-t border-border bg-muted/20">
        <div className="px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Opik Live Feed</span>
            <Badge variant="outline" className="text-xs">
              Disabled
            </Badge>
          </div>
          <Link
            href="/docs/operations/opik"
            className="text-xs text-primary hover:underline flex items-center gap-1"
            target="_blank"
            rel="noopener noreferrer"
          >
            Enable Opik to view traces
            <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="border-t border-border bg-muted/20">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full justify-between px-4 py-2 h-auto"
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Opik Live Feed</span>
            {events.length > 0 && (
              <Badge variant="secondary" className="text-xs">
                {events.length}
              </Badge>
            )}
            {opikTraceUrl && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={(e) => {
                  e.stopPropagation()
                  window.open(opikTraceUrl, "_blank", "noopener,noreferrer")
                }}
              >
                <ExternalLink className="h-3 w-3 mr-1" />
                Full Trace
              </Button>
            )}
          </div>
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronUp className="h-4 w-4" />
          )}
        </Button>

        {isExpanded && (
          <div className="border-t border-border">
            {events.length === 0 && !isLoading ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                No execution events yet. Events will appear here as nodes execute.
              </div>
            ) : (
              <ScrollArea className="h-64" ref={scrollRef}>
                <div className="px-2 py-2 space-y-1">
                  {events.map((event, idx) => (
                    <Card
                      key={`${event.node_name}-${event.timestamp}-${idx}`}
                      className="p-2 cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => setSelectedEvent(event)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          {getStatusIcon(event.status)}
                          <span className="text-sm font-medium truncate">{event.node_name}</span>
                          <Badge
                            variant={event.status === "error" ? "destructive" : "secondary"}
                            className="text-xs"
                          >
                            {event.status}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDuration(event.duration_ms)}
                          </span>
                          <span>{formatTimestamp(event.timestamp)}</span>
                        </div>
                      </div>
                    </Card>
                  ))}
                  {isLoading && events.length === 0 && (
                    <div className="px-4 py-4 text-center text-sm text-muted-foreground">
                      Loading events...
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Event Detail Drawer */}
      <Sheet open={!!selectedEvent} onOpenChange={(open) => !open && setSelectedEvent(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{selectedEvent?.node_name}</SheetTitle>
            <SheetDescription>
              Execution details for {selectedEvent?.timestamp}
            </SheetDescription>
          </SheetHeader>
          {selectedEvent && (
            <div className="mt-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Status</div>
                  <Badge
                    variant={selectedEvent.status === "error" ? "destructive" : "secondary"}
                  >
                    {selectedEvent.status}
                  </Badge>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Duration</div>
                  <div className="text-sm font-medium">{formatDuration(selectedEvent.duration_ms)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Timestamp</div>
                  <div className="text-sm font-medium">
                    {new Date(selectedEvent.timestamp).toLocaleString()}
                  </div>
                </div>
                {selectedEvent.job_id && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Job ID</div>
                    <div className="text-sm font-mono text-xs">{selectedEvent.job_id}</div>
                  </div>
                )}
              </div>
              {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
                <div>
                  <div className="text-xs text-muted-foreground mb-2">Metadata</div>
                  <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
                    {JSON.stringify(selectedEvent.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}

