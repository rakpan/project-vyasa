"use client"

/**
 * Project Row Component (List View)
 * Displays project information in a table row format
 */

import { useRouter } from "next/navigation"
import { Calendar } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { TableRow, TableCell } from "@/components/ui/table"
import { HealthMiniGauge } from "@/components/health-mini-gauge"
import { cn } from "@/lib/utils"
import type { ProjectHubSummary } from "@/types/project"

interface ProjectRowProps {
  project: ProjectHubSummary
  index: number
  onClick?: () => void
}

export function ProjectRow({ project, index, onClick }: ProjectRowProps) {
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
    <TableRow
      key={project.project_id}
      className={cn(
        "cursor-pointer hover:bg-muted/50 transition-colors",
        index % 2 === 0 && "bg-muted/20"
      )}
      onClick={handleClick}
    >
      <TableCell className="font-medium">{project.title}</TableCell>
      <TableCell>
        <Badge variant={rigorVariant} className="text-xs">
          {project.rigor_level}
        </Badge>
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="h-4 w-4" />
          {formatDate(project.last_updated)}
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={statusVariant} className="text-xs">
          {project.status}
        </Badge>
      </TableCell>
      <TableCell>
        <HealthMiniGauge
          manifest={project.manifest_summary}
          openFlagsCount={project.open_flags_count}
          status={project.status}
        />
      </TableCell>
    </TableRow>
  )
}

