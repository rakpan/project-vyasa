/**
 * Tests for Projects Hub Page
 * Tests grouping render, view toggle, filter apply/reset
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { useRouter } from "next/navigation"
import ProjectsPage from "../page"
import * as projectService from "@/services/projectService"

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}))

// Mock project service
jest.mock("@/services/projectService", () => ({
  createProject: jest.fn(),
  listProjectsHub: jest.fn(),
}))

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key]
    }),
    clear: jest.fn(() => {
      store = {}
    }),
  }
})()

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
})

describe("ProjectsPage", () => {
  const mockPush = jest.fn()
  const mockListProjectsHub = projectService.listProjectsHub as jest.MockedFunction<
    typeof projectService.listProjectsHub
  >

  beforeEach(() => {
    jest.clearAllMocks()
    localStorageMock.clear()
    ;(useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
    })
  })

  const mockGrouping = {
    active_research: [
      {
        project_id: "active-1",
        title: "Active Project 1",
        tags: ["security"],
        rigor_level: "exploratory" as const,
        last_updated: "2024-01-15T10:30:00Z",
        status: "Processing" as const,
        open_flags_count: 0,
        manifest_summary: {
          words: 5000,
          claims: 150,
          density: 3.0,
          citations: 25,
          tables: 3,
          figures: 2,
          flags_count_by_type: {},
        },
      },
    ],
    archived_insights: [
      {
        project_id: "archived-1",
        title: "Archived Project 1",
        tags: ["research"],
        rigor_level: "conservative" as const,
        last_updated: "2023-12-01T10:30:00Z",
        status: "Idle" as const,
        open_flags_count: 0,
      },
    ],
  }

  it("renders loading state initially", async () => {
    mockListProjectsHub.mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    render(<ProjectsPage />)

    expect(screen.getByText(/Loading projects/i)).toBeInTheDocument()
  })

  it("renders active research and archived insights sections", async () => {
    mockListProjectsHub.mockResolvedValue(mockGrouping)

    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText("Active Research")).toBeInTheDocument()
      expect(screen.getByText("Archived Insights")).toBeInTheDocument()
    })

    expect(screen.getByText("Active Project 1")).toBeInTheDocument()
    expect(screen.getByText("Archived Project 1")).toBeInTheDocument()
  })

  it("toggles between list and card view", async () => {
    mockListProjectsHub.mockResolvedValue(mockGrouping)

    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText("Active Project 1")).toBeInTheDocument()
    })

    // Should start with list view (default)
    expect(screen.getByRole("table")).toBeInTheDocument()

    // Find and click card view toggle
    const cardToggle = screen.getByLabelText("Card view")
    fireEvent.click(cardToggle)

    // Should switch to card view (no table)
    await waitFor(() => {
      expect(screen.queryByRole("table")).not.toBeInTheDocument()
    })

    // Click list view toggle
    const listToggle = screen.getByLabelText("List view")
    fireEvent.click(listToggle)

    // Should switch back to list view
    await waitFor(() => {
      expect(screen.getByRole("table")).toBeInTheDocument()
    })
  })

  it("applies filters when changed", async () => {
    mockListProjectsHub.mockResolvedValue(mockGrouping)

    render(<ProjectsPage />)

    await waitFor(() => {
      expect(mockListProjectsHub).toHaveBeenCalled()
    })

    // Get initial call
    const initialCall = mockListProjectsHub.mock.calls[0][0]

    // Find search input and type
    const searchInput = screen.getByPlaceholderText(/Search projects/i)
    fireEvent.change(searchInput, { target: { value: "security" } })

    // Wait for debounced filter update
    await waitFor(
      () => {
        expect(mockListProjectsHub).toHaveBeenCalledTimes(2)
      },
      { timeout: 1000 }
    )

    const filterCall = mockListProjectsHub.mock.calls[1][0]
    expect(filterCall?.query).toBe("security")
  })

  it("resets filters when reset button is clicked", async () => {
    mockListProjectsHub.mockResolvedValue(mockGrouping)

    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText("Active Research")).toBeInTheDocument()
    })

    // Set a filter
    const searchInput = screen.getByPlaceholderText(/Search projects/i)
    fireEvent.change(searchInput, { target: { value: "test" } })

    // Open more filters popover
    const moreFiltersButton = screen.getByText(/More Filters/i)
    fireEvent.click(moreFiltersButton)

    // Find and click reset button
    await waitFor(() => {
      const resetButton = screen.getByText(/Reset Filters/i)
      fireEvent.click(resetButton)
    })

    // Search input should be cleared
    await waitFor(() => {
      expect(searchInput).toHaveValue("")
    })
  })

  it("persists view mode preference in localStorage", async () => {
    mockListProjectsHub.mockResolvedValue(mockGrouping)

    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText("Active Research")).toBeInTheDocument()
    })

    // Switch to card view
    const cardToggle = screen.getByLabelText("Card view")
    fireEvent.click(cardToggle)

    // Check localStorage was updated
    await waitFor(() => {
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "vyasa-project-view",
        "card"
      )
    })
  })

  it("restores view mode from localStorage on mount", async () => {
    localStorageMock.setItem("vyasa-project-view", "card")
    mockListProjectsHub.mockResolvedValue(mockGrouping)

    render(<ProjectsPage />)

    await waitFor(() => {
      // Should not have table (card view)
      expect(screen.queryByRole("table")).not.toBeInTheDocument()
    })
  })

  it("shows empty state when no active projects", async () => {
    mockListProjectsHub.mockResolvedValue({
      active_research: [],
      archived_insights: [],
    })

    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText(/No active research projects/i)).toBeInTheDocument()
      expect(screen.getByText(/Create Your First Project/i)).toBeInTheDocument()
    })
  })

  it("shows empty state when no archived projects", async () => {
    mockListProjectsHub.mockResolvedValue({
      active_research: mockGrouping.active_research,
      archived_insights: [],
    })

    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText(/No archived insights yet/i)).toBeInTheDocument()
    })
  })

  it("navigates to project when row is clicked", async () => {
    mockListProjectsHub.mockResolvedValue(mockGrouping)

    render(<ProjectsPage />)

    await waitFor(() => {
      expect(screen.getByText("Active Project 1")).toBeInTheDocument()
    })

    // Click on the project row
    const projectRow = screen.getByText("Active Project 1").closest("tr")
    if (projectRow) {
      fireEvent.click(projectRow)
    }

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/projects/active-1")
    })
  })
})
