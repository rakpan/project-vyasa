"use client"

/**
 * Project Card Component (Card View)
 * Displays project information in a card format
 */

import { useRouter } from "next/navigation"
import { Calendar } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { HealthMiniGauge } from "@/components/health-mini-gauge"
import { cn } from "@/lib/utils"
import type { ProjectHubSummary } from "@/types/project"

interface ProjectCardProps {
  project: ProjectHubSummary
  onClick?: () => void
}

export function ProjectCard({ project, onClick }: ProjectCardProps) {
  const router = useRouter()

  const handleClick = () => {
    if (onClick) {
      onClick()
    } else {
      router.push(`/projects/${project.project_id}`)
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

  const statusVariant = {
    Idle: "secondary" as const,
    Processing: "default" as const,
    AttentionNeeded: "destructive" as const,
  }[project.status]

  const rigorVariant = project.rigor_level === "conservative" ? "default" : "outline"

  return (
    <Card
      className={cn(
        "cursor-pointer hover:shadow-md transition-all hover:border-primary/50",
        project.status === "AttentionNeeded" && "border-amber-300"
      )}
      onClick={handleClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-tight line-clamp-2">
            {project.title}
          </CardTitle>
          <Badge variant={rigorVariant} className="text-xs flex-shrink-0">
            {project.rigor_level}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Status and Health */}
        <div className="flex items-center justify-between gap-2">
          <Badge variant={statusVariant} className="text-xs">
            {project.status}
          </Badge>
          <HealthMiniGauge
            manifest={project.manifest_summary}
            openFlagsCount={project.open_flags_count}
            status={project.status}
          />
        </div>

        {/* Tags */}
        {project.tags && project.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {project.tags.slice(0, 3).map((tag) => (
              <Badge
                key={tag}
                variant="outline"
                className="text-[10px] px-1.5 py-0"
              >
                {tag}
              </Badge>
            ))}
            {project.tags.length > 3 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                +{project.tags.length - 3}
              </Badge>
            )}
          </div>
        )}

        {/* Last Updated */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Calendar className="h-3 w-3" />
          <span>Updated {formatDate(project.last_updated)}</span>
        </div>
      </CardContent>
    </Card>
  )
}

