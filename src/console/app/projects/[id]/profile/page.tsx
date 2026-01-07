"use client"

/**
 * Project Profile Page
 * 
 * Canonical "Project Profile" page showing what the project was created with
 * and allowing editing of key fields with autosave.
 */

import { ProjectProfilePanel } from "@/components/ProjectProfilePanel"
import { useParams } from "next/navigation"

export default function ProjectProfilePage() {
  const params = useParams()
  const projectId = params.id as string

  return <ProjectProfilePanel projectId={projectId} />
}
