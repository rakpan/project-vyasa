"use client"

import React, { useEffect, useCallback, useMemo, useState } from "react"
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Connection,
  addEdge,
  NodeMouseHandler,
  MarkerType,
  EdgeMouseHandler,
  OnNodesDelete,
  OnEdgesDelete,
  OnEdgeUpdateFunc,
} from "reactflow"
import "reactflow/dist/style.css"
import dagre from "dagre"

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Button } from "@/components/ui/button"
import { Quote, ShieldCheck, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels"
import { PdfVerificationView } from "./PdfVerificationView"
import { useResearchStore } from "@/state/useResearchStore"
import { useStoreApi } from "reactflow"
import { MergeAliasDialog } from "./MergeAliasDialog"

interface GraphUpdateEvent {
  type: "graph_update" | "connected" | "complete" | "error"
  timestamp?: string
  step?: string
  nodes?: Array<{
    id: string
    label: string
    type: string
  }>
  edges?: Array<{
    source: string
    target: string
    label: string
    evidence?: string
    confidence?: number
    source_coordinates?: {
      page: number
      bbox: { x1: number; y1: number; x2: number; y2: number }
    }
    is_expert_verified?: boolean
  }>
  status?: string
  message?: string
  job_id?: string
}

interface LiveGraphWorkbenchProps {
  jobId: string
  orchestratorUrl?: string
  pdfUrl?: string
  embedSplit?: boolean
  projectId?: string
}

const CONFIDENCE_LABELS = [
  { threshold: 0.8, label: "High", className: "bg-emerald-600 text-white" },
  { threshold: 0.5, label: "Medium", className: "bg-amber-500 text-white" },
  { threshold: 0, label: "Low", className: "bg-rose-600 text-white" },
]

function getConfidenceVariant(confidence?: number) {
  if (confidence === undefined || confidence === null) {
    return { label: "N/A", className: "bg-gray-500 text-white" }
  }
  const match = CONFIDENCE_LABELS.find((c) => confidence >= c.threshold) || CONFIDENCE_LABELS[2]
  return match
}

// Layout helper using dagre
function getLayoutedElements(nodes: Node[], edges: Edge[]) {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))
  dagreGraph.setGraph({ rankdir: "TB", nodesep: 50, ranksep: 100 })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 150, height: 50 })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 75, // Center the node
        y: nodeWithPosition.y - 25,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

export function LiveGraphWorkbench({ jobId, orchestratorUrl = "/api/proxy/orchestrator", pdfUrl, embedSplit = true, projectId }: LiveGraphWorkbenchProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const { selectedEvidence, setEvidence } = useResearchStore()
  const [isSheetOpen, setIsSheetOpen] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [redlineMode, setRedlineMode] = useState(false)
  const storeApi = useStoreApi()
  const [mergeOpen, setMergeOpen] = useState(false)
  const [mergeSource, setMergeSource] = useState<string | null>(null)
  const [mergeTarget, setMergeTarget] = useState<string | null>(null)

  // Transform backend nodes to React Flow format
  const transformNodes = useCallback((backendNodes: GraphUpdateEvent["nodes"] = []): Node[] => {
    return backendNodes.map((node) => ({
      id: node.id,
      type: "default",
      data: {
        label: node.label,
        type: node.type,
        is_expert_verified: node?.["is_expert_verified"] ?? false,
      },
      position: { x: 0, y: 0 }, // Will be positioned by layout
    }))
  }, [])

  // Transform backend edges to React Flow format
  const transformEdges = useCallback((backendEdges: GraphUpdateEvent["edges"] = []): Edge[] => {
    return backendEdges.map((edge, idx) => ({
      id: `edge-${edge.source}-${edge.target}-${idx}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: "smoothstep",
      animated: true,
      markerEnd: {
        type: MarkerType.ArrowClosed,
      },
      data: {
        evidence: edge.evidence,
        confidence: edge.confidence,
        source_coordinates: edge.source_coordinates,
        is_expert_verified: edge.is_expert_verified ?? false,
      },
    }))
  }, [])

  // Handle graph updates from SSE
  const handleGraphUpdate = useCallback(
    (event: GraphUpdateEvent) => {
      if (event.type === "graph_update" && event.nodes && event.edges) {
        const newNodes = transformNodes(event.nodes)
        const newEdges = transformEdges(event.edges)

        // Merge with existing nodes/edges (avoid duplicates)
        setNodes((nds) => {
          const existingIds = new Set(nds.map((n) => n.id))
          const uniqueNewNodes = newNodes.filter((n) => !existingIds.has(n.id))
          const merged = [...nds, ...uniqueNewNodes]
          return merged
        })

        setEdges((eds) => {
          const existingIds = new Set(eds.map((e) => e.id))
          const uniqueNewEdges = newEdges.filter((e) => !existingIds.has(e.id))
          const merged = [...eds, ...uniqueNewEdges]

          // Apply layout to all nodes
          const allNodes = [...nodes, ...uniqueNewNodes]
          const { nodes: layoutedNodes } = getLayoutedElements(allNodes, merged)
          setNodes(layoutedNodes)

          return merged
        })
      } else if (event.type === "connected") {
        setIsConnected(true)
        setError(null)
      } else if (event.type === "complete") {
        setIsConnected(false)
      } else if (event.type === "error") {
        setError(event.message || "Unknown error")
        setIsConnected(false)
      }
    },
    [transformNodes, transformEdges, setNodes, setEdges, nodes]
  )

  // SSE connection
  useEffect(() => {
    if (!jobId) return

    const eventSource = new EventSource(`${orchestratorUrl}/jobs/${jobId}/stream`)

    eventSource.onmessage = (e) => {
      try {
        const data: GraphUpdateEvent = JSON.parse(e.data)
        handleGraphUpdate(data)
      } catch (err) {
        console.error("Failed to parse SSE event:", err)
      }
    }

    eventSource.onerror = (err) => {
      console.error("SSE connection error:", err)
      setError("Connection lost. Please refresh.")
      setIsConnected(false)
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [jobId, orchestratorUrl, handleGraphUpdate])

  // Handle node click
  const onNodeClick: NodeMouseHandler = useCallback((_event, node) => {
    setSelectedNode(node)
    setIsSheetOpen(true)
  }, [])

  const syncPatch = useCallback(
    async (payload: Record<string, any>) => {
      try {
        await fetch(`${orchestratorUrl}/jobs/${jobId}/extractions`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      } catch (err) {
        console.error("Failed to sync redline patch", err)
      }
    },
    [jobId, orchestratorUrl]
  )

  const onNodesDelete: OnNodesDelete = useCallback(
    (deleted) => {
      if (!redlineMode) return
      setNodes((nds) => nds.filter((n) => !deleted.find((d) => d.id === n.id)))
      syncPatch({ nodes_deleted: deleted.map((d) => d.id) })
    },
    [redlineMode, setNodes, syncPatch]
  )

  const onEdgesDelete: OnEdgesDelete = useCallback(
    (deleted) => {
      if (!redlineMode) return
      setEdges((eds) => eds.filter((e) => !deleted.find((d) => d.id === e.id)))
      syncPatch({ edges_deleted: deleted.map((d) => d.id) })
    },
    [redlineMode, setEdges, syncPatch]
  )

  const onEdgeUpdate: OnEdgeUpdateFunc = useCallback(
    (oldEdge, newConnection) => {
      if (!redlineMode) return
      setEdges((eds) =>
        eds.map((e) => (e.id === oldEdge.id ? { ...e, source: newConnection.source, target: newConnection.target } : e))
      )
      syncPatch({ edge_updated: { id: oldEdge.id, source: newConnection.source, target: newConnection.target } })
    },
    [redlineMode, setEdges, syncPatch]
  )

  const toggleVerifyNode: NodeMouseHandler = useCallback(
    (event, node) => {
      event.preventDefault()
      if (!redlineMode) return
      const nextVerified = !node.data?.is_expert_verified
      setNodes((nds) =>
        nds.map((n) => (n.id === node.id ? { ...n, data: { ...n.data, is_expert_verified: nextVerified } } : n))
      )
      syncPatch({ node_verified: { id: node.id, is_expert_verified: nextVerified } })
    },
    [redlineMode, setNodes, syncPatch]
  )

  const onEdgeContextMenu: EdgeMouseHandler = useCallback(
    (event, edge) => {
      event.preventDefault()
      if (!redlineMode) return
      const nextVerified = !(edge.data?.is_expert_verified ?? false)
      setEdges((eds) =>
        eds.map((e) => (e.id === edge.id ? { ...e, data: { ...e.data, is_expert_verified: nextVerified } } : e))
      )
      syncPatch({ edge_verified: { id: edge.id, is_expert_verified: nextVerified } })
    },
    [redlineMode, setEdges, syncPatch]
  )

  const onEdgeClick: EdgeMouseHandler = useCallback((_event, edge) => {
    const coords = edge.data?.source_coordinates
    if (coords) {
      setEvidence(
        {
          page: coords.page,
          bbox: coords.bbox,
        },
        edge.id
      )
    }
  }, [setEvidence])

  const handleMerge = useCallback(
    async (sourceId: string, targetId: string) => {
      try {
        await syncPatch({ merge: { source_id: sourceId, target_id: targetId, project_id: projectId } })
      } catch (err) {
        console.error("Merge failed", err)
      }
    },
    [syncPatch, projectId]
  )

  // Get edges connected to selected node
  const connectedEdges = useMemo(() => {
    if (!selectedNode) return []
    return edges.filter(
      (edge) => edge.source === selectedNode.id || edge.target === selectedNode.id
    )
  }, [selectedNode, edges])

  // Initial layout when nodes/edges change
  useEffect(() => {
    if (nodes.length > 0 && edges.length > 0) {
      const { nodes: layoutedNodes } = getLayoutedElements(nodes, edges)
      setNodes(layoutedNodes)
    }
  }, [nodes.length, edges.length]) // Only re-layout when count changes

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  )

  const graphPane = (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodesDelete={onNodesDelete}
        onEdgesDelete={onEdgesDelete}
        onEdgeUpdate={onEdgeUpdate}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onNodeContextMenu={toggleVerifyNode}
        onEdgeContextMenu={onEdgeContextMenu}
        onEdgeClick={onEdgeClick}
        fitView
        className="bg-background"
      >
        <Background />
        {/* Toolbar: opacity-0 by default, reveal on hover */}
        <div className="absolute bottom-4 left-4 opacity-0 hover:opacity-100 transition-opacity duration-200 z-10">
          <Controls />
        </div>
        <MiniMap />

        {/* Semantic zoom rendering: Progressive disclosure */}
        {/* Hide badges, snippets, and confidence scores when zoom < 0.5 */}
        {(() => {
          const { zoom } = storeApi.getState().transform
          const showDetails = zoom >= 0.5
          return (
            <style jsx global>{`
              .react-flow__edge-label {
                display: ${showDetails ? "block" : "none"};
              }
              /* Hide confidence badges when zoomed out */
              .confidence-badge {
                display: ${showDetails ? "inline-flex" : "none"};
              }
              /* Hide evidence snippets when zoomed out */
              .evidence-snippet {
                display: ${showDetails ? "block" : "none"};
              }
              /* Show only entity labels when zoomed out */
              .react-flow__node-label {
                font-size: ${showDetails ? "14px" : "12px"};
              }
            `}</style>
          )
        })()}
      </ReactFlow>

      {/* Connection status & redline toggle */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2">
        <Card className="p-2">
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "w-2 h-2 rounded-full",
                isConnected ? "bg-emerald-500" : "bg-gray-400"
              )}
            />
            <span className="text-xs text-muted-foreground">
              {isConnected ? "Live" : "Disconnected"}
            </span>
          </div>
        </Card>
        <Button
          variant={redlineMode ? "default" : "outline"}
          size="sm"
          className="flex items-center gap-1"
          onClick={() => setRedlineMode((v) => !v)}
        >
          <ShieldCheck className="h-4 w-4" />
          {redlineMode ? "Redline Mode On" : "Redline Mode Off"}
        </Button>
        <Card className="p-2 text-xs text-muted-foreground flex items-center gap-2">
          <Trash2 className="h-3 w-3" />
          Right-click to verify; delete/relate when Redline is on.
        </Card>
      </div>

      {/* Error indicator */}
      {error && (
        <div className="absolute top-4 right-4 z-10">
          <Card className="p-2 bg-destructive text-destructive-foreground">
            <p className="text-xs">{error}</p>
          </Card>
        </div>
      )}

      {/* Node details sheet */}
      <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
        <SheetContent side="right" className="w-[400px] sm:w-[540px]">
          <SheetHeader>
            <SheetTitle>{selectedNode?.data?.label || "Node Details"}</SheetTitle>
            <SheetDescription>
              {selectedNode?.data?.type || "entity"} • {connectedEdges.length} connections
            </SheetDescription>
          </SheetHeader>

          <div className="mt-6 space-y-4">
            {/* Outgoing edges */}
            <div>
              <h4 className="text-sm font-semibold mb-2">Outgoing Relations</h4>
              <div className="space-y-2">
                {connectedEdges
                  .filter((edge) => edge.source === selectedNode?.id)
                  .map((edge) => {
                    const confidence = edge.data?.confidence
                    const variant = getConfidenceVariant(confidence)
                    return (
                      <Card key={edge.id} className="p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{edge.label}</span>
                          <Badge className={variant.className}>{variant.label}</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          → {edges.find((e) => e.id === edge.id)?.target}
                        </p>
                        {edge.data?.evidence && (
                          <Collapsible>
                            <CollapsibleTrigger asChild>
                              <Button variant="ghost" size="sm" className="w-full justify-start">
                                <Quote className="h-3 w-3 mr-2" />
                                View Source
                              </Button>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                              <div className="mt-2 p-2 bg-muted rounded text-xs italic border-l-4 border-primary">
                                {edge.data.evidence}
                              </div>
                            </CollapsibleContent>
                          </Collapsible>
                        )}
                      </Card>
                    )
                  })}
                {connectedEdges.filter((edge) => edge.source === selectedNode?.id).length === 0 && (
                  <p className="text-xs text-muted-foreground italic">No outgoing relations</p>
                )}
              </div>
            </div>

            <Separator />

            {/* Incoming edges */}
            <div>
              <h4 className="text-sm font-semibold mb-2">Incoming Relations</h4>
              <div className="space-y-2">
                {connectedEdges
                  .filter((edge) => edge.target === selectedNode?.id)
                  .map((edge) => {
                    const confidence = edge.data?.confidence
                    const variant = getConfidenceVariant(confidence)
                    return (
                      <Card key={edge.id} className="p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{edge.label}</span>
                          <Badge className={variant.className}>{variant.label}</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {edges.find((e) => e.id === edge.id)?.source} →
                        </p>
                        {edge.data?.evidence && (
                          <Collapsible>
                            <CollapsibleTrigger asChild>
                              <Button variant="ghost" size="sm" className="w-full justify-start">
                                <Quote className="h-3 w-3 mr-2" />
                                View Source
                              </Button>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                              <div className="mt-2 p-2 bg-muted rounded text-xs italic border-l-4 border-primary">
                                {edge.data.evidence}
                              </div>
                            </CollapsibleContent>
                          </Collapsible>
                        )}
                      </Card>
                    )
                  })}
                {connectedEdges.filter((edge) => edge.target === selectedNode?.id).length === 0 && (
                  <p className="text-xs text-muted-foreground italic">No incoming relations</p>
                )}
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <MergeAliasDialog
        open={mergeOpen}
        onClose={() => setMergeOpen(false)}
        sourceId={mergeSource}
        targetId={mergeTarget}
        onConfirm={handleMerge}
      />
    </div>
  )

  if (!embedSplit) {
    return graphPane
  }

  return (
    <div className="w-full h-full relative">
      <PanelGroup direction="horizontal" className="h-full">
        <Panel defaultSize={60} minSize={30}>
          {graphPane}
        </Panel>
        <PanelResizeHandle className="w-1 bg-border" />
        <Panel defaultSize={40} minSize={20}>
          <PdfVerificationView fileUrl={pdfUrl || ""} highlight={selectedEvidence} />
        </Panel>
      </PanelGroup>
    </div>
  )
}
