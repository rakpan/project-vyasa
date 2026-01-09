"use client"

/**
 * Perspectives Page - Analytical Notes and Blueprint Management
 * 
 * Two-tab interface:
 * 1. Analytical Notes: List + Editor for perspectives (influence only, not citeable)
 * 2. Blueprint: YAML/JSON paste mode + preview for manuscript structure
 */

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useProjectStore } from "@/state/useProjectStore"
import { Loader2 } from "lucide-react"
import { AnalyticalNotesTab } from "@/components/perspectives/AnalyticalNotesTab"
import { BlueprintTab } from "@/components/perspectives/BlueprintTab"

export default function PerspectivesPage() {
  const params = useParams()
  const projectId = params.id as string
  const { activeProjectId, activeProject, setActiveProject, isLoading, error } = useProjectStore()

  // Sync project context
  useEffect(() => {
    if (projectId && activeProjectId !== projectId) {
      setActiveProject(projectId).catch((err) => {
        console.error("Failed to load project:", err)
      })
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
        <div className="text-center">
          <p className="text-sm text-destructive">Failed to load project</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col">
      <div className="flex-1 overflow-hidden p-6">
        <div className="h-full flex flex-col">
          <div className="mb-4">
            <h1 className="text-2xl font-semibold">Perspectives</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage analytical notes and manuscript blueprint
            </p>
          </div>

          <Tabs defaultValue="notes" className="flex-1 flex flex-col min-h-0">
            <TabsList className="grid w-full grid-cols-2 max-w-md">
              <TabsTrigger value="notes">Analytical Notes</TabsTrigger>
              <TabsTrigger value="blueprint">Blueprint</TabsTrigger>
            </TabsList>

            <TabsContent value="notes" className="flex-1 flex flex-col mt-4 min-h-0">
              <AnalyticalNotesTab projectId={projectId} />
            </TabsContent>

            <TabsContent value="blueprint" className="flex-1 flex flex-col mt-4 min-h-0">
              <BlueprintTab projectId={projectId} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
