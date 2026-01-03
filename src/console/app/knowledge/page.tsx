"use client"

/**
 * Knowledge Base Page - Browse and manage knowledge references
 * Shows all external references that have been ingested into the system
 */

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { BookOpen, ExternalLink, Clock, Search, Filter } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { toast } from "@/hooks/use-toast"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface ExternalReference {
  _key?: string
  reference_id: string
  source_url?: string
  source_name?: string
  title?: string
  project_id?: string
  ingested_at?: string
  extracted_at?: string
  status?: string
  fact_count?: number
  tags?: string[]
}

export default function KnowledgePage() {
  const router = useRouter()
  const [references, setReferences] = useState<ExternalReference[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [filterStatus, setFilterStatus] = useState<string>("all")

  useEffect(() => {
    loadReferences()
  }, [])

  const loadReferences = async () => {
    try {
      setLoading(true)
      // First, fetch all projects to get their IDs
      const projectsResponse = await fetch("/api/proxy/orchestrator/api/projects")
      if (!projectsResponse.ok) {
        throw new Error("Failed to load projects")
      }
      
      const projectsData = await projectsResponse.json()
      const projects = Array.isArray(projectsData) ? projectsData : (projectsData.projects || [])
      
      // Fetch references for each project
      const allReferences: ExternalReference[] = []
      for (const project of projects) {
        try {
          const projectId = project.id || project._key || project.project_id
          if (!projectId) continue
          
          const response = await fetch(
            `/api/proxy/orchestrator/api/knowledge/references?project_id=${projectId}`
          )
          
          if (response.ok) {
            const refs = await response.json()
            if (Array.isArray(refs)) {
              allReferences.push(...refs)
            }
          }
        } catch (err) {
          console.error(`Failed to load references for project ${project.id}:`, err)
          // Continue with other projects
        }
      }
      
      // Sort by extracted_at descending (most recent first)
      allReferences.sort((a, b) => {
        const dateA = a.ingested_at || a.extracted_at || ""
        const dateB = b.ingested_at || b.extracted_at || ""
        return dateB.localeCompare(dateA)
      })
      
      setReferences(allReferences)
    } catch (error) {
      console.error("Failed to load knowledge references:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load knowledge references",
        variant: "destructive",
      })
      setReferences([])
    } finally {
      setLoading(false)
    }
  }

  const filteredReferences = references.filter((ref) => {
    const matchesSearch = 
      !searchQuery ||
      (ref.title || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (ref.source_url || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (ref.reference_id || "").toLowerCase().includes(searchQuery.toLowerCase())
    
    const matchesFilter = 
      filterStatus === "all" ||
      (filterStatus === "pending" && ref.status === "pending") ||
      (filterStatus === "reviewed" && ref.status === "reviewed") ||
      (filterStatus === "promoted" && ref.status === "promoted")
    
    return matchesSearch && matchesFilter
  })

  const handleViewReference = (referenceId: string, projectId?: string) => {
    const url = projectId
      ? `/knowledge/references/${referenceId}?projectId=${projectId}`
      : `/knowledge/references/${referenceId}`
    router.push(url)
  }

  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <BookOpen className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Knowledge Base</h1>
        </div>
        <p className="text-muted-foreground">
          Browse and manage external knowledge references that have been ingested into the system.
        </p>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Knowledge References</CardTitle>
          <CardDescription>
            External research and references that have been processed and are available for review
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Search and Filter */}
          <div className="flex gap-4 mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by title, URL, or reference ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant={filterStatus === "all" ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterStatus("all")}
              >
                All
              </Button>
              <Button
                variant={filterStatus === "pending" ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterStatus("pending")}
              >
                Pending
              </Button>
              <Button
                variant={filterStatus === "reviewed" ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterStatus("reviewed")}
              >
                Reviewed
              </Button>
            </div>
          </div>

          {/* References Table */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary mx-auto mb-4"></div>
                <p className="text-muted-foreground">Loading references...</p>
              </div>
            </div>
          ) : filteredReferences.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-muted-foreground mb-2">
                {references.length === 0
                  ? "No knowledge references found. Ingest external research to get started."
                  : "No references match your search criteria."}
              </div>
              {references.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Use the Research Sideloader in a project to ingest external knowledge.
                </p>
              )}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title / Source</TableHead>
                  <TableHead>Reference ID</TableHead>
                  <TableHead>Project</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Facts</TableHead>
                  <TableHead>Ingested</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredReferences.map((ref) => (
                  <TableRow key={ref._key || ref.reference_id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {ref.source_url && (
                          <ExternalLink className="h-4 w-4 text-muted-foreground" />
                        )}
                        <div>
                          <div className="font-medium">
                            {ref.source_name || ref.title || ref.source_url || "Untitled Reference"}
                          </div>
                          {ref.source_url && (ref.source_name || ref.title) && (
                            <div className="text-xs text-muted-foreground truncate max-w-md">
                              {ref.source_url}
                            </div>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-2 py-1 rounded">
                        {ref.reference_id || ref._key}
                      </code>
                    </TableCell>
                    <TableCell>
                      {ref.project_id ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => router.push(`/projects/${ref.project_id}`)}
                          className="h-auto p-1 text-xs"
                        >
                          {ref.project_id.substring(0, 8)}...
                        </Button>
                      ) : (
                        <span className="text-muted-foreground text-sm">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {ref.status || "unknown"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {ref.fact_count !== undefined ? (
                        <span className="text-sm">{ref.fact_count}</span>
                      ) : (
                        <span className="text-muted-foreground text-sm">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {(ref.ingested_at || ref.extracted_at) ? (
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          {new Date(ref.ingested_at || ref.extracted_at || "").toLocaleDateString()}
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleViewReference(ref.reference_id || ref._key, ref.project_id)}
                      >
                        Review
                      </Button>
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

