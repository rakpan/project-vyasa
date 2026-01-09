"use client"

/**
 * Manuscript Page (Blueprint-Aware)
 * 
 * Dedicated page for viewing and editing the project manuscript.
 * Now includes blueprint sections list with statuses and "Run Section" functionality.
 * Displays compiled manuscript blocks from section runs.
 */

import { useEffect, useMemo, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels"
import { ZenManuscriptEditor } from "@/components/ZenManuscriptEditor"
import { BlueprintSectionsList } from "@/components/manuscript/BlueprintSectionsList"
import { CompiledManuscriptView } from "@/components/manuscript/CompiledManuscriptView"
import { useProjectStore } from "@/state/useProjectStore"
import { Loader2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

export default function ManuscriptPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const projectId = params.id as string
  const jobId = useMemo(() => searchParams.get("jobId") || "", [searchParams])
  
  const {
    activeProjectId,
    activeProject,
    isLoading,
    error,
    setActiveProject,
  } = useProjectStore()
  
  const [manifest, setManifest] = useState<any>(null)
  const [isLoadingManifest, setIsLoadingManifest] = useState(true)
  const [selectedSectionId, setSelectedSectionId] = useState<string | undefined>()
  const [selectedBlockId, setSelectedBlockId] = useState<string | undefined>()
  const [viewMode, setViewMode] = useState<"blueprint" | "legacy">("blueprint")

  // Sync project context
  useEffect(() => {
    if (projectId && activeProjectId !== projectId) {
      setActiveProject(projectId)
    }
  }, [projectId, activeProjectId, setActiveProject])

  // Fetch manifest if jobId is available (for legacy view)
  useEffect(() => {
    if (!jobId || viewMode !== "legacy") {
      setIsLoadingManifest(false)
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
      } catch (err) {
        console.error("Failed to fetch manifest:", err)
      } finally {
        setIsLoadingManifest(false)
      }
    }

    fetchManifest()
    
    // Listen for manifest updates
    const handler = () => {
      try {
        fetchManifest()
      } catch (err) {
        console.error("Error in manifest refresh handler:", err)
      }
    }
    
    if (typeof window !== "undefined") {
      window.addEventListener("refresh-manifest", handler, { passive: true })
    }
    
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("refresh-manifest", handler)
      }
    }
  }, [jobId, viewMode])

  // Handle section run completion
  const handleSectionRun = (sectionId: string, jobId: string) => {
    setSelectedSectionId(sectionId)
    // Refresh compiled view will happen automatically via useEffect in CompiledManuscriptView
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-64px)]">
        <div className="text-center">
          <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading project...</p>
        </div>
      </div>
    )
  }

  if (error || !activeProject) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-64px)]">
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">
              {error || "Project not found"}
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-64px)] overflow-hidden">
      <div className="h-full flex flex-col">
        {/* View Mode Tabs */}
        <div className="px-6 pt-4 pb-2 border-b">
          <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as "blueprint" | "legacy")}>
            <TabsList>
              <TabsTrigger value="blueprint">Blueprint View</TabsTrigger>
              <TabsTrigger value="legacy">Legacy View</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0">
          {viewMode === "blueprint" ? (
            <PanelGroup direction="horizontal" className="h-full">
              {/* Left: Blueprint Sections List */}
              <Panel defaultSize={25} minSize={20} maxSize={40}>
                <div className="h-full border-r">
                  <BlueprintSectionsList
                    projectId={projectId}
                    onSectionRun={handleSectionRun}
                    onSectionSelect={setSelectedSectionId}
                    selectedSectionId={selectedSectionId}
                  />
                </div>
              </Panel>
              <PanelResizeHandle className="w-1 bg-border hover:bg-primary/20 transition-colors" />
              
              {/* Right: Compiled Manuscript View */}
              <Panel defaultSize={75} minSize={60}>
                <div className="h-full">
                  <CompiledManuscriptView
                    projectId={projectId}
                    sectionId={selectedSectionId}
                    onBlockSelect={setSelectedBlockId}
                    selectedBlockId={selectedBlockId}
                  />
                </div>
              </Panel>
            </PanelGroup>
          ) : (
            /* Legacy View: ZenManuscriptEditor */
            <div className="h-full p-6">
              {isLoadingManifest ? (
                <div className="space-y-4">
                  <Skeleton className="h-8 w-48" />
                  <Skeleton className="h-32 w-full" />
                  <Skeleton className="h-32 w-full" />
                </div>
              ) : (
                <ZenManuscriptEditor
                  projectId={projectId}
                  blocks={manifest?.blocks || []}
                  jobId={jobId || undefined}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

