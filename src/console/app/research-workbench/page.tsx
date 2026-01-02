"use client"

import { useMemo, useEffect, useState, Suspense, memo } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels"
import { StrategicInterventionPanel } from "@/components/StrategicInterventionPanel"
import { ZenSourceVault } from "@/components/ZenSourceVault"
import { LiveGraphWorkbench } from "@/components/LiveGraphWorkbench"
import { ZenManuscriptEditor } from "@/components/ZenManuscriptEditor"
import { SparkPulseMini } from "@/components/SparkPulseMini"
import { useResearchStore } from "@/state/useResearchStore"
import { useProjectStore } from "@/state/useProjectStore"
import { Button } from "@/components/ui/button"
import { Maximize2, Minimize2, AlertTriangle, ExternalLink } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/hooks/use-toast"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { InterruptPanel } from "@/components/interrupt-panel"
import { ManifestBar } from "@/components/manifest-bar"
import { ManuscriptHealthTile } from "@/components/manuscript-health-tile"
import { EmptyStateWorkbench } from "@/components/empty-state-workbench"
import { BackendOffline } from "@/components/backend-offline"

/**
 * Skeleton loader component for panes
 */
function PaneSkeleton({ title }: { title: string }) {
  return (
    <div className="h-full flex flex-col p-4 space-y-4">
      <div className="space-y-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-48" />
      </div>
      <div className="flex-1 space-y-3">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-3/4" />
      </div>
    </div>
  )
}

const MemoZenManuscriptEditor = memo(ZenManuscriptEditor)
const MemoLiveGraphWorkbench = memo(LiveGraphWorkbench)

/**
 * Zen-First Research Cockpit
 * 
 * Minimalist, content-focused layout with:
 * - Icon-only navigation sidebar
 * - Auto-hide toolbars
 * - Ghost editor mode (controls only on active block)
 * - Collapsible sidebars (Librarian, Patch)
 * - Focus Mode (hide Source/Graph, expand Manuscript)
 */
function ResearchWorkbenchContent() {
  const params = useSearchParams()
  const router = useRouter()
  const jobId = useMemo(() => params.get("jobId") || "", [params])
  const pdfUrl = useMemo(() => params.get("pdfUrl") || "", [params])
  const projectId = useMemo(() => params.get("projectId") || "", [params])
  const threadId = useMemo(() => params.get("threadId") || "", [params])
  const [guarded, setGuarded] = useState(false)
  const [jobStatus, setJobStatus] = useState<string>("")
  const [diag, setDiag] = useState<any>(null)
  const [isLoadingJob, setIsLoadingJob] = useState(true)
  const { focusMode, toggleFocusMode } = useResearchStore()
  const { activeProjectId, setActiveProject, setActiveJobContext } = useProjectStore()
  const [waitingProposal, setWaitingProposal] = useState<any>(null)
  const neutralityScore = useMemo(() => {
    const flags = diag?.tone_flags ?? 0
    return Math.max(0, 100 - flags * 5)
  }, [diag])

  // Sync projectId from URL with store to ensure correct project context
  useEffect(() => {
    if (projectId && activeProjectId !== projectId) {
      setActiveProject(projectId)
    }
    if (projectId && jobId) {
      setActiveJobContext(jobId, projectId, pdfUrl || null, threadId || jobId)
    }
  }, [projectId, jobId, pdfUrl, threadId, activeProjectId, setActiveProject, setActiveJobContext])

  const handleRescan = async (coords: any) => {
    try {
      await fetch("/cortex/vision/rescan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(coords),
      })
    } catch (err) {
      console.error("Vision rescan failed", err)
    }
  }

  // Single guard: redirect if job/project missing, verify job exists
  useEffect(() => {
    if (!jobId || !projectId) {
      setGuarded(true)
      router.push("/projects")
      toast({
        title: "Select a project/job",
        description: "Workbench requires jobId and projectId. Redirected to Projects.",
      })
      return
    }

    // Verify job exists via status endpoint
    const verifyJob = async () => {
      setIsLoadingJob(true)
      try {
        const response = await fetch(
          `/api/proxy/orchestrator/jobs/${jobId}/status?project_id=${encodeURIComponent(projectId)}`
        )
        
        if (!response.ok) {
          if (response.status === 404) {
            // Job not found
            setGuarded(true)
            router.push("/projects")
            toast({
              title: "Job not found",
              description: "The requested job does not exist. Redirected to Projects.",
              variant: "destructive",
            })
            return
          } else if (response.status === 403) {
            // Project mismatch
            setGuarded(true)
            router.push("/projects")
            toast({
              title: "Job project mismatch",
              description: "The job does not belong to the specified project. Redirected to Projects.",
              variant: "destructive",
            })
            return
          }
          // Other errors - allow to proceed but log
          console.error("Failed to verify job:", response.status, response.statusText)
        }
        const data = await response.json()
        setJobStatus((data?.status || data?.status_out || "").toUpperCase())
        // Job exists and is valid
        setGuarded(false)
      } catch (err) {
        console.error("Error verifying job:", err)
        // On error, allow to proceed (graceful degradation)
        setGuarded(false)
      } finally {
        setIsLoadingJob(false)
      }
    }

    verifyJob()
  }, [jobId, projectId, router])

  // Fetch lightweight diagnostics (best effort)
  useEffect(() => {
    const fetchDiag = async () => {
      if (!jobId) return
      try {
        const resp = await fetch(`/api/proxy/orchestrator/workflow/result/${jobId}`)
        if (!resp.ok) return
        const data = await resp.json()
        const result = data?.result || {}
        const manifest = result?.artifact_manifest || {}
        const conflict = result?.conflict_report || {}
        const counts = manifest?.totals || {}
        const toneFlags =
          Array.isArray(manifest?.flags) && manifest.flags.length
            ? manifest.flags.filter((f: string) => f.toLowerCase().includes("tone")).length
            : 0
        const precisionFlags =
          Array.isArray(manifest?.tables) && manifest.tables.length
            ? manifest.tables.reduce(
                (acc: number, t: any) => acc + (Array.isArray(t.flags) ? t.flags.length : 0),
                0
              )
            : 0
        setDiag({
          opik_trace_url: result?.opik_trace_url,
          critic_status: result?.critic_status || result?.status,
          deadlock: conflict?.deadlock,
          conflict_summary: conflict?.conflict_items?.[0]?.summary,
          unsupported_claims: result?.quality_metrics_after?.unsupported_count,
          tone_flags: toneFlags,
          precision_flags: precisionFlags,
          counts,
          critiques: result?.critiques,
          manifest,
        })
      } catch (e) {
        // ignore
      }
    }
    fetchDiag()
    const handler = () => fetchDiag()
    if (typeof window !== "undefined") {
      window.addEventListener("refresh-manifest", handler)
    }
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("refresh-manifest", handler)
      }
    }
  }, [jobId])

  // Listen for LangGraph interrupts via event stream
  useEffect(() => {
    if (!jobId) return
    const src = new EventSource(`/api/proxy/orchestrator/events/${jobId}`)
    src.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data || "{}")
        if (payload.type === "event" && payload.event === "on_interrupt" && payload.value) {
          setWaitingProposal(payload.value)
        }
      } catch (err) {
        console.debug("Failed to parse event payload", err)
      }
    }
    src.onerror = () => {
      src.close()
    }
    return () => {
      src.close()
    }
  }, [jobId])

  if (guarded) {
    return null
  }

  // Show empty state when no PDF and no job context
  const showEmptyState = !pdfUrl && !jobId && !isLoadingJob
  if (showEmptyState) {
    return <EmptyStateWorkbench />
  }

  const needsSignoff = jobStatus === "NEEDS_SIGNOFF"
  const showDiagnostics =
    jobStatus === "FAILED" || (diag?.critic_status || "").toLowerCase() === "fail" || diag?.deadlock === true
  const opikEnabled = Boolean(diag?.opik_trace_url)

  return (
    <div className="h-full w-full flex flex-col bg-background">
      <InterruptPanel
        jobId={jobId}
        projectId={projectId}
        open={needsSignoff}
        onClose={() => {
          setWaitingProposal(null)
        }}
      />
      {/* Toolbar with Spark Pulse Mini and Focus Mode Toggle */}
      <div className="flex items-center justify-between px-4 py-2 bg-muted/20 border-b border-border/30 group transition-all duration-200 ease-in-out">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold">Research Cockpit</h1>
        </div>
        <div className="flex items-center gap-3 opacity-40 group-hover:opacity-100 transition-opacity duration-200 ease-in-out">
          {showDiagnostics && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (diag?.opik_trace_url) {
                        window.open(diag.opik_trace_url, "_blank", "noopener,noreferrer")
                      }
                    }}
                    disabled={!diag?.opik_trace_url}
                    className="flex items-center gap-2"
                  >
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                    <span className="text-xs">Reasoning Diagnostics</span>
                    {diag?.opik_trace_url && <ExternalLink className="h-3 w-3" />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {diag?.opik_trace_url ? "Open Opik trace in new tab" : "No detailed trace available"}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          <SparkPulseMini />
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleFocusMode}
            className="flex items-center gap-2 transition-all duration-200 ease-in-out"
          >
            {focusMode ? (
              <>
                <Minimize2 className="h-4 w-4" />
                <span className="text-xs">Exit Focus</span>
              </>
            ) : (
              <>
                <Maximize2 className="h-4 w-4" />
                <span className="text-xs">Focus Mode</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Main Content Area */}
      {focusMode ? (
        /* Focus Mode: Manuscript only, centered */
        <div className="flex-1 overflow-hidden">
          <div className="h-full max-w-4xl mx-auto bg-background">
            <ZenManuscriptEditor />
          </div>
        </div>
      ) : (
        /* Normal Mode: Resizable Workbench with adaptive layout */
        <PanelGroup direction="horizontal" className="flex-1">
          {pdfUrl ? (
            /* Three-pane layout: Source/Evidence (Left) | Synthesis/Editor (Center) | Context/Graph (Right) */
            <>
              {/* Pane 1: Source/Evidence (Left) */}
              <Panel 
                defaultSize={35} 
                minSize={15} 
                maxSize={50}
                collapsible={true}
                className="bg-muted/5 border-r border-border/50"
              >
                <Suspense fallback={<PaneSkeleton title="Source/Evidence" />}>
                  <div className="h-full flex flex-col">
                    <div className="px-3 py-2 border-b border-border/50 bg-muted/30">
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Source/Evidence
                      </h3>
                    </div>
                    <div className="flex-1 overflow-hidden">
                      {isLoadingJob ? (
                        <PaneSkeleton title="Loading PDF..." />
                      ) : (
                        <ZenSourceVault fileUrl={pdfUrl} onRescan={handleRescan} projectId={projectId} />
                      )}
                    </div>
                  </div>
                </Suspense>
              </Panel>
              <PanelResizeHandle
                hitAreaMargins={{ coarse: 12, fine: 6 }}
                className="w-2 bg-border/30 hover:bg-border/60 transition-colors cursor-col-resize relative group"
              >
                <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="flex flex-col gap-1">
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                  </span>
                </span>
              </PanelResizeHandle>
              
              {/* Pane 2: Synthesis/Editor (Center) */}
              <Panel 
                defaultSize={40} 
                minSize={30} 
                className="bg-background"
              >
                <Suspense fallback={<PaneSkeleton title="Synthesis/Editor" />}>
                  <div className="h-full flex flex-col">
                    <div className="px-3 py-2 border-b border-border/50 bg-muted/30">
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Synthesis/Editor
                      </h3>
                    </div>
                    <div className="px-3 py-2 border-b border-border/50 space-y-2">
                      <ManifestBar manifest={diag?.manifest} neutralityScore={neutralityScore} />
                      <ManuscriptHealthTile
                        manifest={diag?.manifest}
                        onRefresh={() => window.dispatchEvent(new Event("refresh-manifest"))}
                      />
                    </div>
                    <div className="flex-1 overflow-hidden">
                      {isLoadingJob ? (
                        <PaneSkeleton title="Loading editor..." />
                      ) : (
                        <MemoZenManuscriptEditor key={jobId || "manuscript"} />
                      )}
                    </div>
                  </div>
                </Suspense>
              </Panel>
              <PanelResizeHandle
                hitAreaMargins={{ coarse: 12, fine: 6 }}
                className="w-2 bg-border/30 hover:bg-border/60 transition-colors cursor-col-resize relative group"
              >
                <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="flex flex-col gap-1">
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                  </span>
                </span>
              </PanelResizeHandle>
              
              {/* Pane 3: Context/Graph (Right) */}
              <Panel 
                defaultSize={25} 
                minSize={15} 
                maxSize={40}
                collapsible={true}
                className="bg-muted/5 border-l border-border/50"
              >
                <Suspense fallback={<PaneSkeleton title="Context/Graph" />}>
                  <div className="h-full flex flex-col">
                    <div className="px-3 py-2 border-b border-border/50 bg-muted/30">
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Context/Graph
                      </h3>
                    </div>
                    <div className="flex-1 overflow-hidden">
                      {isLoadingJob ? (
                        <PaneSkeleton title="Loading knowledge graph..." />
                      ) : (
                        <MemoLiveGraphWorkbench key={jobId || "graph"} jobId={jobId} pdfUrl={pdfUrl} embedSplit={false} />
                      )}
                    </div>
                  </div>
                </Suspense>
              </Panel>
            </>
          ) : (
            /* Two-pane layout: Synthesis/Editor (Left) | Context/Graph (Right) - Source pane auto-collapsed */
            <>
              {/* Pane 1: Synthesis/Editor (Left) */}
              <Panel 
                defaultSize={55} 
                minSize={40} 
                className="bg-background"
              >
                <Suspense fallback={<PaneSkeleton title="Synthesis/Editor" />}>
                  <div className="h-full flex flex-col">
                    <div className="px-3 py-2 border-b border-border/50 bg-muted/30">
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Synthesis/Editor
                      </h3>
                    </div>
                    <div className="px-3 py-2 border-b border-border/50">
                      <ManifestBar manifest={diag?.manifest} neutralityScore={neutralityScore} />
                    </div>
                    <div className="flex-1 overflow-hidden">
                      {isLoadingJob ? (
                        <PaneSkeleton title="Loading editor..." />
                      ) : (
                        <MemoZenManuscriptEditor key={jobId || "manuscript"} />
                      )}
                    </div>
                  </div>
                </Suspense>
              </Panel>
              <PanelResizeHandle
                hitAreaMargins={{ coarse: 12, fine: 6 }}
                className="w-2 bg-border/30 hover:bg-border/60 transition-colors cursor-col-resize relative group"
              >
                <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="flex flex-col gap-1">
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                    <span className="h-1 w-[2px] rounded-full bg-border" />
                  </span>
                </span>
              </PanelResizeHandle>
              
              {/* Pane 2: Context/Graph (Right) */}
              <Panel 
                defaultSize={45} 
                minSize={30} 
                maxSize={60}
                collapsible={true}
                className="bg-muted/5 border-l border-border/50"
              >
                <Suspense fallback={<PaneSkeleton title="Context/Graph" />}>
                  <div className="h-full flex flex-col">
                    <div className="px-3 py-2 border-b border-border/50 bg-muted/30">
                      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Context/Graph
                      </h3>
                    </div>
                    <div className="flex-1 overflow-hidden">
                      {isLoadingJob ? (
                        <PaneSkeleton title="Loading knowledge graph..." />
                      ) : (
                        <MemoLiveGraphWorkbench key={jobId || "graph"} jobId={jobId} pdfUrl={pdfUrl} embedSplit={false} />
                      )}
                    </div>
                  </div>
                </Suspense>
              </Panel>
            </>
          )}
        </PanelGroup>
      )}
      {needsSignoff && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-start justify-end p-4">
          <StrategicInterventionPanel jobId={jobId} projectId={projectId} />
        </div>
      )}
      {needsSignoff && (
        <div className="absolute inset-0 z-40 flex items-center justify-center pointer-events-none">
          <div className="bg-destructive/10 text-destructive px-4 py-2 rounded border border-destructive/50 shadow">
            Workflow paused: awaiting strategic intervention signoff.
          </div>
        </div>
      )}
      {showDiagnostics && (
        <div className="px-4 py-2 border-t border-border/30 bg-muted/10">
          <Collapsible>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                <span className="text-sm font-semibold">Why this analysis failed</span>
                {diag?.critic_status && (
                  <Badge variant="outline" className="text-[10px]">
                    {String(diag.critic_status).toUpperCase()}
                  </Badge>
                )}
                {diag?.deadlock && (
                  <Badge variant="destructive" className="text-[10px]">
                    DEADLOCK
                  </Badge>
                )}
              </div>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm" className="text-xs">
                  View details
                </Button>
              </CollapsibleTrigger>
            </div>
            <CollapsibleContent className="mt-2 space-y-2 text-sm text-muted-foreground">
              {diag?.conflict_summary && <div>Conflict: {diag.conflict_summary}</div>}
              {Array.isArray(diag?.critiques) && diag.critiques.length > 0 && (
                <div>Critic: {diag.critiques[0]}</div>
              )}
              <div className="flex flex-wrap gap-4 text-xs">
                <span>Unsupported claims: {diag?.unsupported_claims ?? "n/a"}</span>
                <span>Tone flags: {diag?.tone_flags ?? 0}</span>
                <span>Precision flags: {diag?.precision_flags ?? 0}</span>
              </div>
              {diag?.opik_trace_url && (
                <Button
                  variant="link"
                  size="sm"
                  className="px-0 text-xs"
                  onClick={() => window.open(diag.opik_trace_url, "_blank", "noopener,noreferrer")}
                >
                  View full reasoning trace → Opik
                </Button>
              )}
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}
    </div>
  )
}

export default function ResearchWorkbenchPage() {
  return (
    <Suspense fallback={
      <div className="h-full w-full flex items-center justify-center">
        <div className="space-y-4 text-center">
          <Skeleton className="h-8 w-48 mx-auto" />
          <Skeleton className="h-4 w-32 mx-auto" />
        </div>
      </div>
    }>
      <ResearchWorkbenchContent />
    </Suspense>
  )
}
