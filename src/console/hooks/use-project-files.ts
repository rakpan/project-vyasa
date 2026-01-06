"use client"

import { useEffect, useState, useCallback, useRef } from "react"

interface UseProjectFilesResult {
  files: string[]
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

// Fetches ingested files for a project from the orchestrator proxy endpoint.
export function useProjectFiles(projectId: string | null): UseProjectFilesResult {
  const [files, setFiles] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const fetchFiles = useCallback(async () => {
    if (!projectId) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setIsLoading(true)
    setError(null)
    try {
      // Use the new endpoint that filters ghost records
      const response = await fetch(
        `/api/proxy/orchestrator/api/projects/${projectId}/ingest/files`,
        { signal: controller.signal }
      )
      if (!response.ok) {
        // Fallback to project seed_files if endpoint doesn't exist (backward compatibility)
        if (response.status === 404) {
          const projectResponse = await fetch(
            `/api/proxy/orchestrator/api/projects/${projectId}`,
            { signal: controller.signal }
          )
          if (projectResponse.ok) {
            const project = await projectResponse.json()
            const list = Array.isArray(project.seed_files) ? project.seed_files : []
            setFiles(list)
            return
          }
        }
        throw new Error(`Failed to fetch files (${response.status})`)
      }
      const data = await response.json()
      // Response format: { files: [{ filename, ingestion_id, status, created_at }] }
      const fileList = Array.isArray(data.files) 
        ? data.files.map((f: any) => typeof f === 'string' ? f : f.filename)
        : Array.isArray(data) 
          ? data.map((f: any) => typeof f === 'string' ? f : f.filename)
          : []
      setFiles(fileList)
    } catch (err) {
      if ((err as Error).name === "AbortError") return
      const message = err instanceof Error ? err.message : "Failed to load files"
      setError(message)
      setFiles([])
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    fetchFiles()
    return () => {
      abortRef.current?.abort()
    }
  }, [fetchFiles])

  return { files, isLoading, error, refresh: fetchFiles }
}
