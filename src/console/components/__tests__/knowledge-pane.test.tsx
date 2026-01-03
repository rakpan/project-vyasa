/**
 * Tests for KnowledgePane Component
 * Tests: claim list display, filtering, status transitions
 */

import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { KnowledgePane } from "../knowledge-pane"

// Mock fetch
global.fetch = jest.fn()

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}))

describe("KnowledgePane", () => {
  const mockJobId = "job-123"
  const mockProjectId = "project-123"
  const mockResearchQuestions = ["What is the impact?", "How does it work?"]

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it("renders loading state", () => {
    ;(global.fetch as jest.Mock).mockImplementation(() => new Promise(() => {})) // Never resolves

    render(<KnowledgePane jobId={mockJobId} projectId={mockProjectId} researchQuestions={mockResearchQuestions} />)

    expect(screen.getByText("Knowledge Claims")).toBeInTheDocument()
  })

  it("displays claims after loading", async () => {
    const mockClaims = {
      result: {
        extracted_json: {
          triples: [
            {
              subject: "Subject 1",
              predicate: "predicate",
              object: "Object 1",
              confidence: 0.9,
              is_expert_verified: true,
              source_pointer: { doc_hash: "abc", page: 1 },
              evidence: "Evidence text",
            },
          ],
        },
      },
    }

    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockClaims,
    })

    render(<KnowledgePane jobId={mockJobId} projectId={mockProjectId} researchQuestions={mockResearchQuestions} />)

    await waitFor(() => {
      expect(screen.getByText(/Subject 1 → Object 1/)).toBeInTheDocument()
    })
  })

  it("filters claims by status", async () => {
    const mockClaims = {
      result: {
        extracted_json: {
          triples: [
            {
              subject: "Subject 1",
              predicate: "predicate",
              object: "Object 1",
              confidence: 0.9,
              is_expert_verified: true,
            },
            {
              subject: "Subject 2",
              predicate: "predicate",
              object: "Object 2",
              conflict_flags: ["Conflict"],
            },
          ],
        },
      },
    }

    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockClaims,
    })

    render(<KnowledgePane jobId={mockJobId} projectId={mockProjectId} researchQuestions={mockResearchQuestions} />)

    await waitFor(() => {
      expect(screen.getByText(/Subject 1 → Object 1/)).toBeInTheDocument()
    })

    // Click Flagged filter
    const flaggedButton = screen.getByText(/Flagged/)
    fireEvent.click(flaggedButton)

    await waitFor(() => {
      expect(screen.queryByText(/Subject 1 → Object 1/)).not.toBeInTheDocument()
      expect(screen.getByText(/Subject 2 → Object 2/)).toBeInTheDocument()
    })
  })

  it("shows empty state when no claims", async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        result: {
          extracted_json: {
            triples: [],
          },
        },
      }),
    })

    render(<KnowledgePane jobId={mockJobId} projectId={mockProjectId} researchQuestions={mockResearchQuestions} />)

    await waitFor(() => {
      expect(screen.getByText("No claims available yet.")).toBeInTheDocument()
    })
  })

  it("handles fetch errors", async () => {
    ;(global.fetch as jest.Mock).mockRejectedValueOnce(new Error("Network error"))

    render(<KnowledgePane jobId={mockJobId} projectId={mockProjectId} researchQuestions={mockResearchQuestions} />)

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeInTheDocument()
    })
  })
})

