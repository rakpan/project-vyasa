"use client"

/**
 * New Project Page - Project Creation Wizard
 * Route: /projects/new
 * Single-column focused layout, no sidebar
 */

import { ProjectWizard } from "@/components/project-wizard"
import { useRouter } from "next/navigation"

export default function NewProjectPage() {
  const router = useRouter()

  return (
    <div className="min-h-screen bg-background blueprint-grid">
      <div className="container mx-auto px-4 py-8">
        <ProjectWizard
          onComplete={(projectId) => {
            router.push(`/projects/${projectId}`)
          }}
        />
      </div>
    </div>
  )
}

