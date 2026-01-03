"use client"

/**
 * 3-Pane Research Workbench
 * 
 * Pane 1 (Left): Source/Evidence - PDF Viewer or Text Extraction
 * Pane 2 (Center): Synthesis Editor with pinned Manifest Bar
 * Pane 3 (Right): Context/Knowledge Graph
 * 
 * Uses react-resizable-panels for resizable layout with accessibility support
 */

import { useMemo, useEffect, useState, Suspense } from "react"
import { useParams, useSearchParams, useRouter } from "next/navigation"
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels"
import { ZenSourceVault } from "@/components/ZenSourceVault"
import { ZenManuscriptEditor } from "@/components/ZenManuscriptEditor"
import { LiveGraphWorkbench } from "@/components/LiveGraphWorkbench"
import { ManifestBar } from "@/components/manifest-bar"
import { SeedCorpusZone } from "@/components/seed-corpus-zone"
import { KnowledgePane } from "@/components/knowledge-pane"
import { useProjectStore } from "@/state/useProjectStore"
import { toast } from "@/hooks/use-toast"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertTriangle } from "lucide-react"
import { EvidenceProvider, useEvidence } from "@/contexts/evidence-context"
import { OpikLiveFeedPanel } from "@/components/opik-live-feed-panel"
import { RigorToggleModal } from "@/components/rigor-toggle-modal"

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
      </div>
    </div>
  )
}

// Wrapper component to use evidence context
function EvidenceSourceVault({ fileUrl, onRescan, projectId }: { fileUrl: string; onRescan: (coords: any) => void; projectId: string }) {
  const { highlight } = useEvidence()
  return <ZenSourceVault fileUrl={fileUrl} highlight={highlight} onRescan={onRescan} projectId={projectId} />
}

function ProjectWorkbenchContent() {
  const params = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()
  const projectId = params.id as string
  const jobId = useMemo(() => searchParams.get("jobId") || "", [searchParams])
  const pdfUrl = useMemo(() => searchParams.get("pdfUrl") || "", [searchParams])
  const threadId = useMemo(() => searchParams.get("threadId") || "", [searchParams])
  
  const { activeProjectId, activeProject, setActiveProject, setActiveJobContext } = useProjectStore()
  const [manifest, setManifest] = useState<any>(null)
  const [neutralityScore, setNeutralityScore] = useState(100)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [opikTraceUrl, setOpikTraceUrl] = useState<string | null>(null)
  const [rigorModalOpen, setRigorModalOpen] = useState(false)

  // Sync project context
  useEffect(() => {
    if (projectId && activeProjectId !== projectId) {
      setActiveProject(projectId).catch((err) => {
        console.error("Failed to load project:", err)
        setError("Failed to load project")
      })
    }
    if (projectId && jobId) {
      setActiveJobContext(jobId, projectId, pdfUrl || null, threadId || jobId)
    }
  }, [projectId, jobId, pdfUrl, threadId, activeProjectId, setActiveProject, setActiveJobContext])

  // Fetch manifest and diagnostics
  useEffect(() => {
    if (!jobId) {
      setIsLoading(false)
      return
    }

    const fetchManifest = async () => {
      try {
        const resp = await fetch(`/api/proxy/orchestrator/workflow/result/${jobId}`)
        if (!resp.ok) {
          throw new Error(`Failed to fetch manifest: ${resp.status}`)
        }
        const data = await resp.json()
        const result = data?.result || {}
        const manifestData = result?.artifact_manifest || {}
        
        setManifest(manifestData)
        setOpikTraceUrl(result?.opik_trace_url || null)
        
        // Calculate neutrality score
        const toneFlags = Array.isArray(manifestData?.blocks)
          ? manifestData.blocks.reduce((acc: number, block: any) => {
              return acc + (Array.isArray(block.tone_flags) ? block.tone_flags.length : 0)
            }, 0)
          : 0
        const score = Math.max(0, 100 - toneFlags * 5)
        setNeutralityScore(score)
        
        setIsLoading(false)
      } catch (err: any) {
        console.error("Failed to fetch manifest:", err)
        setError(err?.message || "Failed to load workbench data")
        setIsLoading(false)
      }
    }

    fetchManifest()
    
    // Listen for manifest updates
    const handler = () => fetchManifest()
    if (typeof window !== "undefined") {
      window.addEventListener("refresh-manifest", handler)
    }
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("refresh-manifest", handler)
      }
    }
  }, [jobId])

  if (error) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <Alert variant="destructive" className="max-w-md">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="h-full w-full flex flex-col bg-background">
      {/* Seed Corpus Dropzone - Spans top of left+center panes */}
      <div className="px-4 py-3 border-b border-border bg-muted/20">
        <SeedCorpusZone projectId={projectId} />
      </div>

      {/* 3-Pane Resizable Layout */}
      <PanelGroup direction="horizontal" className="flex-1 min-h-0">
        {/* Pane 1: Source/Evidence (PDF Viewer or Text Extraction) */}
        <Panel defaultSize={30} minSize={20} maxSize={50}>
          <div className="h-full flex flex-col border-r border-border">
            <div className="px-4 py-2 border-b border-border bg-muted/30">
              <h2 className="text-sm font-semibold text-foreground">Source / Evidence</h2>
            </div>
            <div className="flex-1 overflow-auto">
              {isLoading ? (
                <PaneSkeleton title="Source" />
              ) : pdfUrl ? (
                <EvidenceSourceVault
                  fileUrl={pdfUrl}
                  onRescan={async (coords) => {
                    try {
                      await fetch("/cortex/vision/rescan", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(coords),
                      })
                    } catch (err) {
                      console.error("Vision rescan failed", err)
                    }
                  }}
                  projectId={projectId}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-sm text-muted-foreground p-8">
                  <div className="text-center">
                    <p className="mb-2">No source document available</p>
                    <p className="text-xs">Upload a PDF or start a job to view source material</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Panel>

        {/* Resize Handle with accessibility */}
        <PanelResizeHandle 
          className="w-1 bg-border hover:bg-primary/20 transition-colors"
          hitAreaMargins={{ coarse: 12, fine: 6 }}
        />

        {/* Pane 2: Synthesis Editor with pinned Manifest Bar */}
        <Panel defaultSize={40} minSize={30} maxSize={60}>
          <div className="h-full flex flex-col border-r border-border">
            {/* Pinned Manifest Bar */}
            <div className="px-4 py-2 border-b border-border bg-background sticky top-0 z-10">
              {isLoading ? (
                <Skeleton className="h-8 w-full" />
              ) : (
                <div className="flex items-center justify-between gap-2">
                  <ManifestBar manifest={manifest} neutralityScore={neutralityScore} />
                  {activeProject && (
                    <button
                      onClick={() => setRigorModalOpen(true)}
                      className="px-2 py-1 text-xs rounded-md border border-border hover:bg-muted transition-colors capitalize"
                      title="Click to change rigor level"
                    >
                      {activeProject.rigor_level || "exploratory"}
                    </button>
                  )}
                </div>
              )}
            </div>
            
            {/* Editor Content */}
            <div className="flex-1 overflow-auto">
              {isLoading ? (
                <PaneSkeleton title="Synthesis Editor" />
              ) : jobId ? (
                <Suspense fallback={<PaneSkeleton title="Synthesis Editor" />}>
                  <ZenManuscriptEditor
                    projectId={projectId}
                    blocks={manifest?.blocks || []}
                    jobId={jobId}
                  />
                </Suspense>
              ) : (
                <div className="h-full flex items-center justify-center text-sm text-muted-foreground p-8">
                  <div className="text-center">
                    <p className="mb-2">No active job</p>
                    <p className="text-xs">Start a research job to begin synthesis</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Panel>

        {/* Resize Handle with accessibility */}
        <PanelResizeHandle 
          className="w-1 bg-border hover:bg-primary/20 transition-colors"
          hitAreaMargins={{ coarse: 12, fine: 6 }}
        />

        {/* Pane 3: Context/Knowledge Graph */}
        <Panel defaultSize={30} minSize={20} maxSize={50}>
          <div className="h-full flex flex-col">
            <div className="px-4 py-2 border-b border-border bg-muted/30">
              <h2 className="text-sm font-semibold text-foreground">Knowledge Claims</h2>
            </div>
            <div className="flex-1 overflow-hidden">
              {isLoading ? (
                <PaneSkeleton title="Knowledge Claims" />
              ) : jobId ? (
                <KnowledgePane
                  jobId={jobId}
                  projectId={projectId}
                  researchQuestions={activeProject?.research_questions || []}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-sm text-muted-foreground p-8">
                  <div className="text-center">
                    <p className="mb-2">No knowledge claims available</p>
                    <p className="text-xs">Start a research job to view extracted knowledge</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Panel>
      </PanelGroup>
      
      {/* Opik Live Feed Panel (collapsible bottom panel) */}
      <OpikLiveFeedPanel
        jobId={jobId}
        opikEnabled={!!opikTraceUrl}
        opikTraceUrl={opikTraceUrl || undefined}
      />
      
      {/* Rigor Toggle Modal */}
      {activeProject && (
        <RigorToggleModal
          open={rigorModalOpen}
          onClose={() => setRigorModalOpen(false)}
          currentRigor={(activeProject.rigor_level as "exploratory" | "conservative") || "exploratory"}
          projectId={projectId}
          onRigorChanged={(newRigor) => {
            // Update local project state
            if (activeProject) {
              activeProject.rigor_level = newRigor
            }
            // Refresh project from store
            setActiveProject(projectId).catch((err) => {
              console.error("Failed to refresh project after rigor change:", err)
            })
          }}
        />
      )}
    </div>
  )
}

export default function ProjectWorkbenchPage() {
  return (
    <EvidenceProvider>
      <ProjectWorkbenchContent />
    </EvidenceProvider>
  )
}
