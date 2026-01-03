/**
 * Tests for Seed Corpus Zone Component
 * Tests: drop creates cards, status transitions render, retry triggers API call
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { useRouter } from "next/navigation"
import { SeedCorpusZone } from "../seed-corpus-zone"
import * as projectService from "@/services/projectService"

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}))

// Mock fetch
global.fetch = jest.fn()

// Mock toast
jest.mock("@/hooks/use-toast", () => ({
  toast: jest.fn(),
}))

describe("SeedCorpusZone", () => {
  const mockPush = jest.fn()
  const mockFetch = global.fetch as jest.MockedFunction<typeof fetch>

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
    })
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: "test-job-123" }),
    } as Response)
  })

  it("renders dropzone when no jobs", () => {
    render(<SeedCorpusZone projectId="test-project" />)
    expect(screen.getByText(/drop pdf files here/i)).toBeInTheDocument()
  })

  it("creates card when file is dropped", async () => {
    render(<SeedCorpusZone projectId="test-project" />)

    const dropzone = screen.getByLabelText(/drop pdf files here/i)
    const file = new File(["test content"], "test.pdf", { type: "application/pdf" })

    // Simulate drop
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    })

    // Wait for card to appear
    await waitFor(() => {
      expect(screen.getByText("test.pdf")).toBeInTheDocument()
    })
  })

  it("shows status transitions", async () => {
    render(<SeedCorpusZone projectId="test-project" />)

    const dropzone = screen.getByLabelText(/drop pdf files here/i)
    const file = new File(["test content"], "test.pdf", { type: "application/pdf" })

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    })

    // Initially should show Queued
    await waitFor(() => {
      expect(screen.getByText("test.pdf")).toBeInTheDocument()
    })

    // Mock job status response for Extracting
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        job: {
          status: "RUNNING",
          current_step: "cartographer",
          progress: 0.3,
        },
      }),
    } as Response)

    // Wait for status update
    await waitFor(
      () => {
        expect(screen.getByText(/extracting/i)).toBeInTheDocument()
      },
      { timeout: 3000 }
    )
  })

  it("shows retry button for failed jobs", async () => {
    render(<SeedCorpusZone projectId="test-project" />)

    const dropzone = screen.getByLabelText(/drop pdf files here/i)
    const file = new File(["test content"], "test.pdf", { type: "application/pdf" })

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    })

    // Mock failed job status
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        job: {
          status: "FAILED",
          error: "Processing failed",
        },
      }),
    } as Response)

    await waitFor(
      () => {
        expect(screen.getByText(/retry/i)).toBeInTheDocument()
      },
      { timeout: 3000 }
    )
  })

  it("triggers API call on retry", async () => {
    render(<SeedCorpusZone projectId="test-project" />)

    const dropzone = screen.getByLabelText(/drop pdf files here/i)
    const file = new File(["test content"], "test.pdf", { type: "application/pdf" })

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    })

    // Mock failed job
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        job: {
          status: "FAILED",
          error: "Processing failed",
        },
      }),
    } as Response)

    await waitFor(() => {
      expect(screen.getByText(/retry/i)).toBeInTheDocument()
    })

    const retryButton = screen.getByText(/retry/i)
    fireEvent.click(retryButton)

    // Should trigger new upload
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/workflow/submit"),
        expect.objectContaining({
          method: "POST",
        })
      )
    })
  })

  it("shows global banner when jobs are active", async () => {
    render(<SeedCorpusZone projectId="test-project" />)

    const dropzone = screen.getByLabelText(/drop pdf files here/i)
    const file = new File(["test content"], "test.pdf", { type: "application/pdf" })

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    })

    // Mock running job
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        job: {
          status: "RUNNING",
          current_step: "cartographer",
          progress: 0.3,
        },
      }),
    } as Response)

    await waitFor(() => {
      expect(screen.getByText(/processing/i)).toBeInTheDocument()
    })
  })
})

