"use client"

/**
 * Evidence Engine - 2-Pane Research Interface
 * Evidence (Left) → Knowledge Graph View (Right)
 * 
 * This is the main in-project workspace for viewing evidence and knowledge.
 * For the full 3-pane workbench with PDF viewer and manuscript editor, see /projects/[id]/workbench
 */

import { useEffect } from "react"
import { useParams } from "next/navigation"
import { Loader2 } from "lucide-react"
import { useProjectStore } from "@/state/useProjectStore"
import { EvidenceDock } from "@/components/EvidenceDock"
import { KnowledgeStream } from "@/components/KnowledgeStream"
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
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      {/* Left Pane: Evidence Dock (25%) */}
      <div className="w-1/4 flex-shrink-0">
        <EvidenceDock projectId={projectId} />
      </div>

      {/* Right Pane: Knowledge Stream (Graph View) - Expanded to fill remaining space */}
      <div className="flex-1 min-w-0">
        <KnowledgeStream projectId={projectId} />
      </div>
    </div>
  )
}
