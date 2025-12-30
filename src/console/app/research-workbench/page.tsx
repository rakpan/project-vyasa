"use client"

import { useMemo } from "react"
import { useSearchParams } from "next/navigation"
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels"
import { ZenSourceVault } from "@/components/ZenSourceVault"
import { LiveGraphWorkbench } from "@/components/LiveGraphWorkbench"
import { ZenManuscriptEditor } from "@/components/ZenManuscriptEditor"
import { SparkPulseMini } from "@/components/SparkPulseMini"
import { ZenNavigation } from "@/components/ZenNavigation"
import { useResearchStore } from "@/state/useResearchStore"
import { Button } from "@/components/ui/button"
import { Maximize2, Minimize2 } from "lucide-react"
import { cn } from "@/lib/utils"

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
  const jobId = useMemo(() => params.get("jobId") || "", [params])
  const pdfUrl = useMemo(() => params.get("pdfUrl") || "", [params])
  const projectId = useMemo(() => params.get("projectId") || "", [params])
  const { focusMode, toggleFocusMode } = useResearchStore()

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

  // Workbench Guards: Show placeholder if jobId or projectId are missing
  if (!jobId || !projectId) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-background">
        <div className="text-center space-y-4 max-w-md">
          <h2 className="text-2xl font-semibold">Project Not Selected</h2>
          <p className="text-muted-foreground">
            Please select a project and start a job to view the research workbench.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen w-full flex flex-col bg-background">
      {/* Minimal Header with Spark Pulse Mini */}
      <div className="flex items-center justify-between px-6 py-3 bg-muted/20 border-b border-border/30 group">
        <div className="flex items-center gap-4">
          <ZenNavigation />
          <h1 className="text-lg font-semibold">Research Cockpit</h1>
        </div>
        <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
          <SparkPulseMini />
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleFocusMode}
            className="flex items-center gap-2"
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
      {(!jobId || !projectId || !pdfUrl) ? (
        <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
          Missing jobId/projectId/pdfUrl. Provide all query params to load the cockpit.
        </div>
      ) : focusMode ? (
        /* Focus Mode: Manuscript only, centered */
        <div className="flex-1 overflow-hidden">
          <div className="h-full max-w-4xl mx-auto bg-background">
            <ZenManuscriptEditor />
          </div>
        </div>
      ) : (
        /* Normal Mode: Three-pane layout */
        <PanelGroup direction="horizontal" className="flex-1">
          {/* Pane 1: Source Vault */}
          <Panel defaultSize={30} minSize={20} className="bg-muted/10">
            <ZenSourceVault fileUrl={pdfUrl} onRescan={handleRescan} />
          </Panel>

          {/* Subtle Resize Handle */}
          <PanelResizeHandle className="w-1 bg-muted/40 hover:bg-muted/60 transition-colors" />

          {/* Pane 2: Graph */}
          <Panel defaultSize={40} minSize={20} className="bg-muted/10">
            <LiveGraphWorkbench jobId={jobId} pdfUrl={pdfUrl} embedSplit={false} />
          </Panel>

          {/* Subtle Resize Handle */}
          <PanelResizeHandle className="w-1 bg-muted/40 hover:bg-muted/60 transition-colors" />

          {/* Pane 3: Manuscript Kernel */}
          <Panel defaultSize={30} minSize={20} className="bg-background">
            <ZenManuscriptEditor />
          </Panel>
        </PanelGroup>
      )}
    </div>
  )
}
