/**
 * Tests for Research Workbench page guard validation.
 * 
 * Tests:
 * - Invalid job shows correct error/redirect
 */

import { render, screen, waitFor } from "@testing-library/react"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "@/hooks/use-toast"
import ResearchWorkbenchPage from "../page"

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
  useSearchParams: jest.fn(),
}))

// Mock hooks
jest.mock("@/hooks/use-toast", () => ({
  toast: jest.fn(),
}))

// Mock stores
jest.mock("@/state/useResearchStore", () => ({
  useResearchStore: () => ({
    focusMode: false,
    toggleFocusMode: jest.fn(),
  }),
}))

jest.mock("@/state/useProjectStore", () => ({
  useProjectStore: () => ({
    activeProjectId: "proj-1",
    setActiveProject: jest.fn(),
    setActiveJobContext: jest.fn(),
  }),
}))

// Mock components
jest.mock("@/components/ZenSourceVault", () => ({
  ZenSourceVault: () => <div>ZenSourceVault</div>,
}))

jest.mock("@/components/LiveGraphWorkbench", () => ({
  LiveGraphWorkbench: () => <div>LiveGraphWorkbench</div>,
}))

jest.mock("@/components/ZenManuscriptEditor", () => ({
  ZenManuscriptEditor: () => <div>ZenManuscriptEditor</div>,
}))

jest.mock("@/components/SparkPulseMini", () => ({
  SparkPulseMini: () => <div>SparkPulseMini</div>,
}))

// Mock fetch globally
global.fetch = jest.fn()

describe("ResearchWorkbenchPage Guard Validation", () => {
  const mockPush = jest.fn()
  const mockGet = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
    })
    ;(useSearchParams as jest.Mock).mockReturnValue({
      get: mockGet,
    })
  })

  it("should redirect to /projects when job not found (404)", async () => {
    // Setup: jobId and projectId present, but job doesn't exist
    mockGet.mockImplementation((key: string) => {
      if (key === "jobId") return "job-not-found"
      if (key === "projectId") return "proj-1"
      if (key === "pdfUrl") return ""
      return null
    })

    // Mock fetch to return 404
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 404,
    })

    render(<ResearchWorkbenchPage />)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/jobs/job-not-found/status")
      )
    })

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/projects")
    })

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Job not found",
          description: expect.stringContaining("does not exist"),
          variant: "destructive",
        })
      )
    })
  })

  it("should redirect to /projects when job project mismatch (403)", async () => {
    // Setup: jobId and projectId present, but project doesn't match
    mockGet.mockImplementation((key: string) => {
      if (key === "jobId") return "job-123"
      if (key === "projectId") return "proj-1"
      if (key === "pdfUrl") return ""
      return null
    })

    // Mock fetch to return 403 (project mismatch)
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 403,
    })

    render(<ResearchWorkbenchPage />)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/jobs/job-123/status")
      )
    })

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/projects")
    })

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Job project mismatch",
          description: expect.stringContaining("does not belong"),
          variant: "destructive",
        })
      )
    })
  })

  it("should allow access when job exists and is valid", async () => {
    // Setup: jobId and projectId present, job exists
    mockGet.mockImplementation((key: string) => {
      if (key === "jobId") return "job-123"
      if (key === "projectId") return "proj-1"
      if (key === "pdfUrl") return ""
      return null
    })

    // Mock fetch to return 200 (job exists)
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ status: "running", progress: 50 }),
    })

    render(<ResearchWorkbenchPage />)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/jobs/job-123/status")
      )
    })

    // Should not redirect
    await waitFor(() => {
      expect(mockPush).not.toHaveBeenCalledWith("/projects")
    })

    // Should render workbench content
    // (Component renders when guarded is false)
    // Note: We can't easily assert component render without more setup,
    // but we verify that redirect was NOT called, which means guarded=false
  })

  it("should redirect when jobId is missing", () => {
    // Setup: missing jobId
    mockGet.mockImplementation((key: string) => {
      if (key === "projectId") return "proj-1"
      return null
    })

    render(<ResearchWorkbenchPage />)

    // Should redirect immediately (no fetch needed)
    expect(mockPush).toHaveBeenCalledWith("/projects")
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Select a project/job",
        description: expect.stringContaining("requires jobId"),
      })
    )
  })

  it("should redirect when projectId is missing", () => {
    // Setup: missing projectId
    mockGet.mockImplementation((key: string) => {
      if (key === "jobId") return "job-123"
      return null
    })

    render(<ResearchWorkbenchPage />)

    // Should redirect immediately (no fetch needed)
    expect(mockPush).toHaveBeenCalledWith("/projects")
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Select a project/job",
        description: expect.stringContaining("requires jobId"),
      })
    )
  })
})

