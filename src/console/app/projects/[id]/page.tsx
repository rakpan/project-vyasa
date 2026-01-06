"use client"

/**
 * Project Workbench Page - 3-Pane Research Interface
 * Evidence (Left) → Processing (Center) → Product (Right)
 */

import { useEffect } from "react"
import { useParams } from "next/navigation"
import { Loader2 } from "lucide-react"
import { useProjectStore } from "@/state/useProjectStore"
import { EvidenceDock } from "@/components/EvidenceDock"
import { KnowledgeStream } from "@/components/KnowledgeStream"
import { ManuscriptLab } from "@/components/ManuscriptLab"
import { Card, CardContent } from "@/components/ui/card"

export default function ProjectWorkbenchPage() {
  const params = useParams()
  const projectId = params.id as string
  const {
    activeProjectId,
    activeProject,
    isLoading,
    error,
    setActiveProject,
  } = useProjectStore()

  // Ensure active project matches route param
  useEffect(() => {
    if (projectId && activeProjectId !== projectId) {
      setActiveProject(projectId)
    }
  }, [projectId, activeProjectId, setActiveProject])

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
    <div className="grid grid-cols-12 h-[calc(100vh-64px)] overflow-hidden">
      {/* Left Pane: Evidence Dock (25%) */}
      <div className="col-span-3">
        <EvidenceDock projectId={projectId} />
      </div>

      {/* Center Pane: Knowledge Stream (42%) */}
      <div className="col-span-5">
        <KnowledgeStream projectId={projectId} />
      </div>

      {/* Right Pane: Manuscript Lab (33%) */}
      <div className="col-span-4">
        <ManuscriptLab projectId={projectId} />
      </div>
    </div>
  )
}
