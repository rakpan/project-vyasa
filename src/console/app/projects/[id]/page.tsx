"use client"

/**
 * Project Workbench Page - 3-column dashboard for project work.
 * Left: Seed Corpus (file list + uploader)
 * Center: Processing (extraction results / graph view)
 * Right: Intent Context (thesis, RQs, anti-scope)
 */

import { useEffect } from "react"
import { useParams } from "next/navigation"
import { FileText, Target, BookOpen } from "lucide-react"
import { useProjectStore } from "@/state/useProjectStore"
import { FileUploader } from "@/components/FileUploader"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

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

  // Refresh project after upload to get updated seed_files
  const handleUploadComplete = () => {
    if (projectId) {
      setActiveProject(projectId)
    }
  }

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-6">
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">Loading project...</p>
        </div>
      </div>
    )
  }

  if (error || !activeProject) {
    return (
      <div className="container mx-auto px-4 py-6">
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
    <div className="container mx-auto px-4 py-6 max-w-[1600px]">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold mb-1">{activeProject.title}</h1>
        <p className="text-sm text-muted-foreground">
          Created {new Date(activeProject.created_at).toLocaleDateString()}
        </p>
      </div>

      {/* 3-Column Grid Layout */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column: Seed Corpus (25%) */}
        <div className="col-span-12 md:col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Seed Corpus
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Uploader */}
              <FileUploader
                projectId={projectId}
                onUploadComplete={handleUploadComplete}
                onUploadError={(error) => {
                  console.error(`Upload error: ${error}`)
                }}
              />

              {/* File List */}
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Files ({activeProject.seed_files.length})
                </p>
                {activeProject.seed_files.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No files uploaded yet
                  </p>
                ) : (
                  <div className="space-y-1">
                    {activeProject.seed_files.map((filename, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between text-xs p-2 rounded border border-border/30 bg-muted/20 hover:bg-muted/40"
                      >
                        <span className="truncate flex-1">{filename}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Center Column: Processing (50%) */}
        <div className="col-span-12 md:col-span-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Target className="h-4 w-4" />
                Processing
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  Extraction results and graph visualization will appear here
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  TODO: Integrate graph view component
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Intent Context (25%) */}
        <div className="col-span-12 md:col-span-3 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BookOpen className="h-4 w-4" />
                Intent Context
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Thesis */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Thesis
                </p>
                <p className="text-sm leading-relaxed">{activeProject.thesis}</p>
              </div>

              {/* Research Questions */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Research Questions
                </p>
                <ul className="space-y-2">
                  {activeProject.research_questions.map((rq, idx) => (
                    <li key={idx} className="text-sm flex items-start gap-2">
                      <span className="text-muted-foreground mt-1">•</span>
                      <span className="flex-1">{rq}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Anti-Scope */}
              {activeProject.anti_scope && activeProject.anti_scope.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Anti-Scope
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {activeProject.anti_scope.map((item, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Target Journal */}
              {activeProject.target_journal && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Target Journal
                  </p>
                  <Badge variant="secondary" className="text-xs">
                    {activeProject.target_journal}
                  </Badge>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

