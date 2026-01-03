"use client"

/**
 * Projects Hub - Portfolio Command Center
 * Lists all research projects with grouping, filtering, and view toggles.
 */

import { useEffect, useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import { Plus, List, Grid3x3, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { toast } from "@/hooks/use-toast"
import { ProjectFiltersComponent, type ProjectFilters } from "@/components/project-filters"
import { ProjectRow } from "@/components/project-row"
import { ProjectCard } from "@/components/project-card"
import { listProjectsHub } from "@/services/projectService"
import type { ProjectGrouping } from "@/types/project"

type ViewMode = "list" | "card"

const STORAGE_KEY_FILTERS = "vyasa-project-filters"
const STORAGE_KEY_VIEW = "vyasa-project-view"

export default function ProjectsPage() {
  const router = useRouter()
  const [grouping, setGrouping] = useState<ProjectGrouping | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>("list")
  const [filters, setFilters] = useState<ProjectFilters>(() => {
    // Restore filters from localStorage
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(STORAGE_KEY_FILTERS)
      if (saved) {
        try {
          return JSON.parse(saved)
        } catch {
          // Invalid JSON, use defaults
        }
      }
    }
    return {
      query: "",
      tags: [],
      rigor: null,
      status: null,
      from: "",
      to: "",
    }
  })

  // Restore view mode from localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(STORAGE_KEY_VIEW)
      if (saved === "card" || saved === "list") {
        setViewMode(saved)
      }
    }
  }, [])

  // Persist filters to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_FILTERS, JSON.stringify(filters))
    }
  }, [filters])

  // Persist view mode to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_VIEW, viewMode)
    }
  }, [viewMode])

  // Fetch projects with hub view
  const fetchProjects = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await listProjectsHub({
        query: filters.query || undefined,
        tags: filters.tags.length > 0 ? filters.tags : undefined,
        rigor: filters.rigor || undefined,
        status: filters.status || undefined,
        from: filters.from || undefined,
        to: filters.to || undefined,
        include_manifest: true, // Always include manifest for health indicators
      })
      setGrouping(result)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load projects"
      setError(errorMessage)
      console.error("Failed to fetch projects:", err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])

  const hasActiveProjects = grouping && grouping.active_research.length > 0
  const hasArchivedProjects = grouping && grouping.archived_insights.length > 0

  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="text-2xl font-semibold flex-shrink-0">Research Projects</h1>
        <div className="flex items-center gap-2">
          {/* View Toggle */}
          <ToggleGroup
            type="single"
            value={viewMode}
            onValueChange={(value) => {
              if (value === "list" || value === "card") {
                setViewMode(value)
              }
            }}
            className="border rounded-md"
          >
            <ToggleGroupItem value="list" aria-label="List view">
              <List className="h-4 w-4" />
            </ToggleGroupItem>
            <ToggleGroupItem value="card" aria-label="Card view">
              <Grid3x3 className="h-4 w-4" />
            </ToggleGroupItem>
          </ToggleGroup>

          {/* New Project Button */}
          <Button
            className="flex-shrink-0"
            onClick={() => router.push("/projects/new")}
          >
            <Plus className="h-4 w-4 mr-2" />
            New Project
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="mb-6">
        <ProjectFiltersComponent
          filters={filters}
          onFiltersChange={setFilters}
        />
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6 border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading projects...</span>
        </div>
      )}

      {/* Active Research Section */}
      {!isLoading && (
        <div className="space-y-6">
          <section>
            <h2 className="text-lg font-semibold mb-4">Active Research</h2>
            {hasActiveProjects ? (
              viewMode === "list" ? (
                <Card>
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Title</TableHead>
                          <TableHead>Rigor</TableHead>
                          <TableHead>Last Updated</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Health</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {grouping.active_research.map((project, index) => (
                          <ProjectRow
                            key={project.project_id}
                            project={project}
                            index={index}
                          />
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {grouping.active_research.map((project) => (
                    <ProjectCard key={project.project_id} project={project} />
                  ))}
                </div>
              )
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <p className="text-sm text-muted-foreground mb-4">
                    No active research projects
                  </p>
                  <Button
                    variant="outline"
                    onClick={() => router.push("/projects/new")}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Create Your First Project
                  </Button>
                </CardContent>
              </Card>
            )}
          </section>

          {/* Archived Insights Section */}
          <section>
            <h2 className="text-lg font-semibold mb-4">Archived Insights</h2>
            {hasArchivedProjects ? (
              viewMode === "list" ? (
                <Card>
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Title</TableHead>
                          <TableHead>Rigor</TableHead>
                          <TableHead>Last Updated</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Health</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {grouping.archived_insights.map((project, index) => (
                          <ProjectRow
                            key={project.project_id}
                            project={project}
                            index={index}
                          />
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {grouping.archived_insights.map((project) => (
                    <ProjectCard key={project.project_id} project={project} />
                  ))}
                </div>
              )
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <p className="text-sm text-muted-foreground">
                    No archived insights yet
                  </p>
                </CardContent>
              </Card>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
