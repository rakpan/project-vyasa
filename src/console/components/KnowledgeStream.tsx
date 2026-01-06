"use client"

/**
 * Knowledge Stream - Center Pane (42% width)
 * Shows live feed of agent actions and graph view
 */

import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Activity,
  Network,
  FileText,
  Sparkles,
  CheckCircle2,
  Clock,
} from "lucide-react"

interface AgentAction {
  id: string
  timestamp: string
  agent: "Cartographer" | "Librarian" | "Logician" | "Synthesizer" | "Critic"
  action: string
  metadata?: {
    claims_count?: number
    page?: number
    section?: string
  }
}

interface KnowledgeStreamProps {
  projectId: string
}

export function KnowledgeStream({ projectId }: KnowledgeStreamProps) {
  const [activeTab, setActiveTab] = useState<"feed" | "graph">("feed")
  const [actions, setActions] = useState<AgentAction[]>([])

  // TODO: Connect to real-time event stream or polling
  // For now, show empty state

  const getAgentIcon = (agent: AgentAction["agent"]) => {
    switch (agent) {
      case "Cartographer":
        return <Network className="h-4 w-4" />
      case "Librarian":
        return <FileText className="h-4 w-4" />
      case "Logician":
        return <Sparkles className="h-4 w-4" />
      case "Synthesizer":
        return <FileText className="h-4 w-4" />
      case "Critic":
        return <CheckCircle2 className="h-4 w-4" />
      default:
        return <Activity className="h-4 w-4" />
    }
  }

  return (
    <div className="flex flex-col h-full border-r border-slate-200">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "feed" | "graph")} className="flex-1 flex flex-col">
        <div className="flex-shrink-0 border-b border-slate-200 px-4 pt-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="feed">Live Feed</TabsTrigger>
            <TabsTrigger value="graph">Graph View</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="feed" className="flex-1 flex flex-col m-0 mt-0 min-h-0">
          <div className="flex-1 overflow-y-auto p-4">
            {actions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                  <Activity className="h-8 w-8 text-slate-400" />
                </div>
                <h3 className="text-sm font-semibold mb-2">Waiting for evidence...</h3>
                <p className="text-xs text-muted-foreground max-w-xs">
                  Drop files to begin processing. Agent actions will appear here in real-time.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {actions.map((action) => (
                  <Card key={action.id} className="border-slate-200">
                    <CardContent className="p-3">
                      <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 mt-0.5">
                          {getAgentIcon(action.agent)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className="text-[10px]">
                              {action.agent}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground">
                              {new Date(action.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="text-xs text-foreground">{action.action}</p>
                          {action.metadata && (
                            <div className="flex gap-2 mt-2 text-[10px] text-muted-foreground">
                              {action.metadata.claims_count !== undefined && (
                                <span>{action.metadata.claims_count} claims</span>
                              )}
                              {action.metadata.page !== undefined && (
                                <span>Page {action.metadata.page}</span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="graph" className="flex-1 flex flex-col m-0 mt-0 min-h-0">
          <div className="flex-1 overflow-y-auto p-4">
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <Network className="h-8 w-8 text-slate-400" />
              </div>
              <h3 className="text-sm font-semibold mb-2">Graph View</h3>
              <p className="text-xs text-muted-foreground max-w-xs">
                Interactive knowledge graph visualization coming soon.
              </p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

