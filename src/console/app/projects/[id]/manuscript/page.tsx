"use client"

/**
 * Manuscript Page
 * 
 * Dedicated page for viewing and editing the project manuscript.
 * Displays the manuscript editor with blocks, citations, and claims.
 */

import { useEffect, useMemo, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"
import { ZenManuscriptEditor } from "@/components/ZenManuscriptEditor"
import { useProjectStore } from "@/state/useProjectStore"
import { Loader2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

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

  // Sync project context
  useEffect(() => {
    if (projectId && activeProjectId !== projectId) {
      setActiveProject(projectId)
    }
  }, [projectId, activeProjectId, setActiveProject])

  // Fetch manifest if jobId is available
  useEffect(() => {
    if (!jobId) {
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
  }, [jobId])

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
    </div>
  )
}

