"use client"

import { useMemo, useEffect, useState } from "react"
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
import { Maximize2, Minimize2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/hooks/use-toast"

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
export default function ResearchWorkbenchPage() {
  const params = useSearchParams()
  const router = useRouter()
  const jobId = useMemo(() => params.get("jobId") || "", [params])
  const pdfUrl = useMemo(() => params.get("pdfUrl") || "", [params])
  const projectId = useMemo(() => params.get("projectId") || "", [params])
  const [guarded, setGuarded] = useState(false)
  const [jobStatus, setJobStatus] = useState<string>("")
  const { focusMode, toggleFocusMode } = useResearchStore()
  const { activeProjectId, setActiveProject, setActiveJobContext } = useProjectStore()

  // Sync projectId from URL with store to ensure correct project context
  useEffect(() => {
    if (projectId && activeProjectId !== projectId) {
      setActiveProject(projectId)
    }
    if (projectId && jobId) {
      setActiveJobContext(jobId, projectId, pdfUrl || null)
    }
  }, [projectId, jobId, pdfUrl, activeProjectId, setActiveProject, setActiveJobContext])

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
      }
    }

    verifyJob()
  }, [jobId, projectId, router])

  if (guarded) {
    return null
  }

  const needsSignoff = jobStatus === "NEEDS_SIGNOFF"

  return (
    <div className="h-full w-full flex flex-col bg-background">
      {/* Toolbar with Spark Pulse Mini and Focus Mode Toggle */}
      <div className="flex items-center justify-between px-4 py-2 bg-muted/20 border-b border-border/30 group transition-all duration-200 ease-in-out">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold">Research Cockpit</h1>
        </div>
        <div className="flex items-center gap-3 opacity-40 group-hover:opacity-100 transition-opacity duration-200 ease-in-out">
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
        /* Normal Mode: Conditional layout based on pdfUrl */
        <PanelGroup direction="horizontal" className="flex-1">
          {pdfUrl ? (
            /* Three-pane layout: 40% Source | 30% Knowledge | 30% Manuscript */
            <>
              <Panel defaultSize={40} minSize={20} className="bg-muted/10 transition-all duration-200 ease-in-out">
                <ZenSourceVault fileUrl={pdfUrl} onRescan={handleRescan} projectId={projectId} />
              </Panel>
              <PanelResizeHandle className="w-1 bg-muted/40 hover:bg-muted/60 transition-colors duration-200 ease-in-out" />
              <Panel defaultSize={30} minSize={20} className="bg-muted/10 transition-all duration-200 ease-in-out">
                <LiveGraphWorkbench jobId={jobId} pdfUrl={pdfUrl} embedSplit={false} />
              </Panel>
              <PanelResizeHandle className="w-1 bg-muted/40 hover:bg-muted/60 transition-colors duration-200 ease-in-out" />
              <Panel defaultSize={30} minSize={20} className="bg-background transition-all duration-200 ease-in-out">
                <ZenManuscriptEditor />
              </Panel>
            </>
          ) : (
            /* Two-pane layout: 50% Knowledge | 50% Manuscript (no PDF panel) */
            <>
              <Panel defaultSize={50} minSize={20} className="bg-muted/10 transition-all duration-200 ease-in-out">
                <LiveGraphWorkbench jobId={jobId} pdfUrl={pdfUrl} embedSplit={false} />
              </Panel>
              <PanelResizeHandle className="w-1 bg-muted/40 hover:bg-muted/60 transition-colors duration-200 ease-in-out" />
              <Panel defaultSize={50} minSize={20} className="bg-background transition-all duration-200 ease-in-out">
                <ZenManuscriptEditor />
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
    </div>
  )
}
