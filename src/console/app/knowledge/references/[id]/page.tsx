"use client"

import { useParams, useSearchParams } from "next/navigation"
import { ReferenceReviewPanel } from "@/components/ReferenceReviewPanel"
import { useRouter } from "next/navigation"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useEffect, useState, Suspense } from "react"

function ReferenceReviewContent() {
  const params = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()
  const referenceId = params.id as string
  const [projectId, setProjectId] = useState<string | null>(null)

  // Try to get projectId from query params or fetch from reference
  useEffect(() => {
    const projectIdParam = searchParams.get("projectId")
    if (projectIdParam) {
      setProjectId(projectIdParam)
    } else {
      // Fetch reference to get project_id
      fetch(`/api/proxy/orchestrator/api/knowledge/references/${referenceId}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.reference?.project_id) {
            setProjectId(data.reference.project_id)
          }
        })
        .catch((err) => {
          console.error("Failed to fetch reference project_id:", err)
        })
    }
  }, [referenceId, searchParams])

  const handlePromoted = () => {
    // Navigate back to project page after promotion
    if (projectId) {
      router.push(`/projects/${projectId}`)
    }
  }

  const handleRejected = () => {
    // Navigate back to project page after rejection
    if (projectId) {
      router.push(`/projects/${projectId}`)
    }
  }

  const handleBack = () => {
    // Use explicit navigation instead of router.back()
    if (projectId) {
      router.push(`/projects/${projectId}`)
    } else {
      router.push("/projects")
    }
  }

  return (
    <div className="container mx-auto px-4 py-6 max-w-6xl">
      <div className="mb-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleBack}
          className="flex items-center gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
      </div>

      <ReferenceReviewPanel
        referenceId={referenceId}
        onPromoted={handlePromoted}
        onRejected={handleRejected}
      />
    </div>
  )
}

export default function ReferenceReviewPage() {
  return (
    <Suspense fallback={<div className="container mx-auto px-4 py-6 max-w-6xl">Loading...</div>}>
      <ReferenceReviewContent />
    </Suspense>
  )
}

