"use client"

/**
 * Project Profile Panel Component
 * 
 * Editable project configuration panel with autosave.
 * Fields:
 * - Title (editable)
 * - Status (editable dropdown)
 * - Rigor (editable dropdown)
 * - Tags (chips input)
 * - Research Questions (editable list with add/remove)
 * - Last updated (read-only)
 * - createdAt / createdBy (read-only) if present
 */

import { useState, useEffect, useCallback, useMemo } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Loader2, Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { getProject } from "@/services/projectService"
import { useProjectStore } from "@/state/useProjectStore"
import type { ProjectConfig } from "@/types/project"
import { toast } from "@/hooks/use-toast"

interface ProjectProfilePanelProps {
  projectId: string
}

export function ProjectProfilePanel({ projectId }: ProjectProfilePanelProps) {
  const router = useRouter()
  const { updateProject: updateProjectInStore } = useProjectStore()
  const [project, setProject] = useState<ProjectConfig | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Form state
  const [title, setTitle] = useState("")
  const [rigor, setRigor] = useState<"exploratory" | "conservative">("exploratory")
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState("")
  const [researchQuestions, setResearchQuestions] = useState<string[]>([])
  const [newRq, setNewRq] = useState("")
  
  // Track if there are unsaved changes
  const hasUnsavedChanges = useMemo(() => {
    if (!project) return false
    return (
      title !== (project.title || "") ||
      rigor !== (project.rigor_level || "exploratory") ||
      JSON.stringify(researchQuestions) !== JSON.stringify(project.research_questions || []) ||
      JSON.stringify(tags) !== JSON.stringify(project.tags || [])
    )
  }, [title, rigor, researchQuestions, tags, project])

  // Load project data
  useEffect(() => {
    let cancelled = false
    
    async function loadProject() {
      setIsLoading(true)
      setError(null)
      try {
        const data = await getProject(projectId)
        if (!cancelled) {
          setProject(data)
          setTitle(data.title || "")
          setRigor(data.rigor_level || "exploratory")
          // Tags and status come from hub view, not ProjectConfig
          // We'll need to fetch them separately or add to ProjectConfig
          setTags([]) // TODO: Add tags to ProjectConfig or fetch separately
          setResearchQuestions(data.research_questions || [])
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Failed to load project"
          setError(message)
          toast({
            title: "Failed to load project",
            description: message,
            variant: "destructive",
          })
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }
    
    loadProject()
    return () => {
      cancelled = true
    }
  }, [projectId])

  // Save function using store action
  const saveProject = useCallback(async (updates: Partial<ProjectConfig>) => {
    if (!project) return
    
    setIsSaving(true)
    setError(null)
    
    try {
      // Use store action which updates activeProject and projects list
      const updated = await updateProjectInStore(projectId, updates)
      setProject(updated)
      // Update local state to match
      if (updates.title !== undefined) setTitle(updated.title)
      if (updates.rigor_level !== undefined) setRigor(updated.rigor_level)
      if (updates.research_questions !== undefined) setResearchQuestions(updated.research_questions)
      if (updates.tags !== undefined) setTags(updated.tags || [])
      
      toast({
        title: "Project updated",
        description: "Your changes have been saved successfully.",
        variant: "default",
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save project"
      setError(message)
      toast({
        title: "Failed to save",
        description: message,
        variant: "destructive",
      })
      // Rollback optimistic update
      if (project) {
        if (updates.title !== undefined) setTitle(project.title)
        if (updates.rigor_level !== undefined) setRigor(project.rigor_level || "exploratory")
        if (updates.research_questions !== undefined) setResearchQuestions(project.research_questions || [])
        if (updates.tags !== undefined) setTags(project.tags || [])
      }
    } finally {
      setIsSaving(false)
    }
  }, [project, projectId, updateProjectInStore])

  // Handle update button click - save all changes
  const handleUpdate = () => {
    if (!hasUnsavedChanges || !project) return
    
    const updates: Partial<ProjectConfig> = {}
    if (title !== (project.title || "")) {
      updates.title = title.trim()
    }
    if (rigor !== (project.rigor_level || "exploratory")) {
      updates.rigor_level = rigor
    }
    if (JSON.stringify(researchQuestions) !== JSON.stringify(project.research_questions || [])) {
      updates.research_questions = researchQuestions
    }
    if (JSON.stringify(tags) !== JSON.stringify(project.tags || [])) {
      updates.tags = tags
    }
    
    saveProject(updates)
  }

  // Handle tag input
  const handleTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && tagInput.trim()) {
      e.preventDefault()
      const newTag = tagInput.trim()
      if (!tags.includes(newTag)) {
        setTags([...tags, newTag])
        setTagInput("")
      }
    }
  }

  const removeTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove))
  }

  // Handle research question add
  const handleAddRq = () => {
    if (!newRq.trim()) return
    setResearchQuestions([...researchQuestions, newRq.trim()])
    setNewRq("")
  }

  // Handle research question remove
  const handleRemoveRq = (index: number) => {
    setResearchQuestions(researchQuestions.filter((_, i) => i !== index))
  }

  // Handle research question edit
  const handleRqChange = (index: number, value: string) => {
    const updated = [...researchQuestions]
    updated[index] = value
    setResearchQuestions(updated)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-64px)]">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error && !project) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-64px)]">
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-64px)]">
        <p className="text-muted-foreground">Project not found</p>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-6 max-w-4xl">
      {/* Header with Back button and Update button */}
      <div className="flex items-center justify-between mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push(`/projects/${projectId}`)}
          className="gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Project
        </Button>
        <div className="flex items-center gap-3">
          {isSaving && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Saving...</span>
            </div>
          )}
          <Button
            onClick={handleUpdate}
            disabled={!hasUnsavedChanges || isSaving}
            className="gap-2"
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Update"
            )}
          </Button>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <Card className="mb-6 border-destructive/50 bg-destructive/5">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="space-y-6">
        {/* Title */}
        <Card>
          <CardHeader>
            <CardTitle>Title</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Project title"
              className="min-h-[60px] w-full"
            />
          </CardContent>
        </Card>

        {/* Rigor Level */}
        <Card>
          <CardHeader>
            <CardTitle>Rigor Level</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={rigor} onValueChange={setRigor}>
              <SelectTrigger className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="exploratory">Exploratory</SelectItem>
                <SelectItem value="conservative">Conservative</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Tags */}
        <Card>
          <CardHeader>
            <CardTitle>Tags</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleTagKeyDown}
                placeholder="Add a tag and press Enter"
                className="max-w-md"
              />
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="gap-1">
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeTag(tag)}
                        className="ml-1 hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Research Questions */}
        <Card>
          <CardHeader>
            <CardTitle>Research Questions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {researchQuestions.map((rq, index) => (
                <div key={index} className="flex items-start gap-2">
                  <span className="text-sm text-muted-foreground mt-2 shrink-0">
                    {index + 1}.
                  </span>
                  <Textarea
                    value={rq}
                    onChange={(e) => handleRqChange(index, e.target.value)}
                    placeholder="Research question"
                    className="flex-1 min-h-[60px]"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemoveRq(index)}
                    className="mt-1 shrink-0 text-destructive hover:text-destructive"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              <div className="flex items-start gap-2">
                <span className="text-sm text-muted-foreground mt-2 shrink-0">
                  {researchQuestions.length + 1}.
                </span>
                <div className="flex-1 flex gap-2">
                  <Input
                    value={newRq}
                    onChange={(e) => setNewRq(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault()
                        handleAddRq()
                      }
                    }}
                    placeholder="Add a research question"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleAddRq}
                    disabled={!newRq.trim()}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Created With - Read-only creation-time metadata */}
        <Card>
          <CardHeader>
            <CardTitle>Created With</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {project.created_at && (
              <div>
                <span className="text-muted-foreground">Created At: </span>
                <span>{new Date(project.created_at).toLocaleString()}</span>
              </div>
            )}
            {project.created_by && (
              <div>
                <span className="text-muted-foreground">Created By: </span>
                <span>{project.created_by}</span>
              </div>
            )}
            {/* Note: rigor_level, seed_files, anti_scope, target_journal can be edited,
                so they're not truly "creation-time" metadata. Only show if we had
                a createdWith object with initial values. */}
            {project.seed_files && project.seed_files.length > 0 && (
              <div>
                <span className="text-muted-foreground">Initial Seed Files: </span>
                <span>{project.seed_files.length} file{project.seed_files.length !== 1 ? "s" : ""}</span>
                <ul className="mt-1 ml-4 list-disc text-xs text-muted-foreground">
                  {project.seed_files.slice(0, 5).map((file, idx) => (
                    <li key={idx}>{file}</li>
                  ))}
                  {project.seed_files.length > 5 && (
                    <li className="text-muted-foreground/70">
                      ... and {project.seed_files.length - 5} more
                    </li>
                  )}
                </ul>
              </div>
            )}
            {/* Show message if no creation metadata available */}
            {!project.created_at && !project.created_by && (!project.seed_files || project.seed_files.length === 0) && (
              <p className="text-xs text-muted-foreground italic">
                No creation-time metadata available.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Read-only metadata */}
        <Card>
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>
              <span className="text-muted-foreground">Project ID: </span>
              <span className="font-mono text-xs">{project.project_id || project.id}</span>
            </div>
            {project.last_updated && (
              <div>
                <span className="text-muted-foreground">Last Updated: </span>
                <span>{new Date(project.last_updated).toLocaleString()}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

