"use client"

/**
 * Projects Home Page - Lists all research projects and allows creating new ones.
 * Dense, functional engineering tool design.
 */

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Plus, Calendar, FileText } from "lucide-react"
import { useProjectStore } from "@/state/useProjectStore"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ProjectCreate } from "@/types/project"

export default function ProjectsPage() {
  const router = useRouter()
  const { projects, isLoading, error, fetchProjects, createProject } = useProjectStore()
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formData, setFormData] = useState<ProjectCreate>({
    title: "",
    thesis: "",
    research_questions: [],
    anti_scope: null,
    target_journal: null,
    seed_files: null,
  })
  const [rqText, setRqText] = useState("")
  const [antiScopeText, setAntiScopeText] = useState("")

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const handleCreateProject = async () => {
    if (!formData.title.trim() || !formData.thesis.trim()) {
      return
    }

    // Parse research questions (one per line)
    const rqs = rqText
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)

    if (rqs.length === 0) {
      return
    }

    // Parse anti-scope (one per line, optional)
    const antiScope = antiScopeText
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)

    setIsSubmitting(true)
    try {
      const newProject = await createProject({
        ...formData,
        research_questions: rqs,
        anti_scope: antiScope.length > 0 ? antiScope : null,
      })

      // Reset form
      setFormData({
        title: "",
        thesis: "",
        research_questions: [],
        anti_scope: null,
        target_journal: null,
        seed_files: null,
      })
      setRqText("")
      setAntiScopeText("")
      setIsDialogOpen(false)

      // Navigate to workbench
      router.push(`/projects/${newProject.id}`)
    } catch (error) {
      console.error("Failed to create project:", error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString)
      return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    } catch {
      return isoString
    }
  }

  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Research Projects</h1>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" />
              New Project
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create New Project</DialogTitle>
              <DialogDescription>
                Define your research intent: thesis, questions, and scope.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label htmlFor="title" className="text-sm font-medium">
                  Title <span className="text-destructive">*</span>
                </label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) =>
                    setFormData({ ...formData, title: e.target.value })
                  }
                  placeholder="e.g., Security Analysis of Web Applications"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="thesis" className="text-sm font-medium">
                  Thesis <span className="text-destructive">*</span>
                </label>
                <Textarea
                  id="thesis"
                  value={formData.thesis}
                  onChange={(e) =>
                    setFormData({ ...formData, thesis: e.target.value })
                  }
                  placeholder="The core argument or hypothesis..."
                  rows={4}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="research_questions" className="text-sm font-medium">
                  Research Questions <span className="text-destructive">*</span>
                </label>
                <Textarea
                  id="research_questions"
                  value={rqText}
                  onChange={(e) => setRqText(e.target.value)}
                  placeholder="One question per line..."
                  rows={4}
                />
                <p className="text-xs text-muted-foreground">
                  Enter one research question per line
                </p>
              </div>
              <div className="space-y-2">
                <label htmlFor="anti_scope" className="text-sm font-medium">
                  Anti-Scope (Optional)
                </label>
                <Textarea
                  id="anti_scope"
                  value={antiScopeText}
                  onChange={(e) => setAntiScopeText(e.target.value)}
                  placeholder="Explicitly out-of-scope topics (one per line)..."
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="target_journal" className="text-sm font-medium">
                  Target Journal (Optional)
                </label>
                <Input
                  id="target_journal"
                  value={formData.target_journal || ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      target_journal: e.target.value || null,
                    })
                  }
                  placeholder="e.g., IEEE Security & Privacy"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateProject}
                disabled={
                  isSubmitting ||
                  !formData.title.trim() ||
                  !formData.thesis.trim() ||
                  rqText.trim().split("\n").filter((l) => l.trim()).length === 0
                }
              >
                {isSubmitting ? "Creating..." : "Create Project"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6 border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Projects Table */}
      <Card>
        <CardHeader>
          <CardTitle>Projects</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              Loading projects...
            </div>
          ) : projects.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              No projects yet. Create your first project to get started.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Files</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.map((project) => (
                  <TableRow
                    key={project.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => router.push(`/projects/${project.id}`)}
                  >
                    <TableCell className="font-medium">{project.title}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Calendar className="h-4 w-4" />
                        {formatDate(project.created_at)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <FileText className="h-4 w-4" />
                        {/* TODO: Fetch and display actual file count from project.seed_files */}
                        {0}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

