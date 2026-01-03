/**
 * Tests for Project Creation Wizard Component
 * Tests: cannot advance without RQ, template applies, rigor preview changes
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { useRouter } from "next/navigation"
import { ProjectWizard } from "../project-wizard"
import * as projectService from "@/services/projectService"
import { PROJECT_TEMPLATES } from "@/data/project-templates"

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}))

// Mock project service
jest.mock("@/services/projectService", () => ({
  createProject: jest.fn(),
  updateRigor: jest.fn(),
}))

describe("ProjectWizard", () => {
  const mockPush = jest.fn()
  const mockCreateProject = projectService.createProject as jest.MockedFunction<
    typeof projectService.createProject
  >
  const mockUpdateRigor = projectService.updateRigor as jest.MockedFunction<
    typeof projectService.updateRigor
  >

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
    })
    mockCreateProject.mockResolvedValue({
      id: "test-project-id",
      title: "Test Project",
      thesis: "Test thesis",
      research_questions: ["RQ1"],
      created_at: new Date().toISOString(),
      seed_files: [],
    } as any)
    mockUpdateRigor.mockResolvedValue({} as any)
  })

  it("cannot advance from step 1 without RQ", () => {
    render(<ProjectWizard />)

    // Fill title and thesis
    const titleInput = screen.getByLabelText(/title/i)
    const thesisInput = screen.getByLabelText(/thesis/i)

    fireEvent.change(titleInput, { target: { value: "Test Title" } })
    fireEvent.change(thesisInput, { target: { value: "Test Thesis" } })

    // Next button should be disabled (no RQ)
    const nextButton = screen.getByRole("button", { name: /next/i })
    expect(nextButton).toBeDisabled()

    // Add an RQ
    const rqInput = screen.getByPlaceholderText(/enter a research question/i)
    fireEvent.change(rqInput, { target: { value: "What is the impact?" } })
    fireEvent.click(screen.getByRole("button", { name: /add/i }))

    // Now Next should be enabled
    expect(nextButton).not.toBeDisabled()
  })

  it("applies template when selected", async () => {
    render(<ProjectWizard />)

    // Go to step 2
    const titleInput = screen.getByLabelText(/title/i)
    const thesisInput = screen.getByLabelText(/thesis/i)
    fireEvent.change(titleInput, { target: { value: "Test" } })
    fireEvent.change(thesisInput, { target: { value: "Test" } })

    // Add RQ to proceed
    const rqInput = screen.getByPlaceholderText(/enter a research question/i)
    fireEvent.change(rqInput, { target: { value: "RQ1" } })
    fireEvent.click(screen.getByRole("button", { name: /add/i }))
    fireEvent.click(screen.getByRole("button", { name: /next/i }))

    // Select a template
    await waitFor(() => {
      const templateSelect = screen.getByRole("combobox")
      expect(templateSelect).toBeInTheDocument()
    })

    const templateSelect = screen.getByRole("combobox")
    fireEvent.click(templateSelect)

    // Select first template
    await waitFor(() => {
      const templateOption = screen.getByText(new RegExp(PROJECT_TEMPLATES[0].name, "i"))
      fireEvent.click(templateOption)
    })

    // Template should populate RQs and anti-scope
    await waitFor(() => {
      const template = PROJECT_TEMPLATES[0]
      template.suggested_rqs.forEach((rq) => {
        expect(screen.getByText(rq)).toBeInTheDocument()
      })
    })
  })

  it("rigor preview changes with rigor level", async () => {
    render(<ProjectWizard />)

    // Navigate to step 3
    const titleInput = screen.getByLabelText(/title/i)
    const thesisInput = screen.getByLabelText(/thesis/i)
    fireEvent.change(titleInput, { target: { value: "Test" } })
    fireEvent.change(thesisInput, { target: { value: "Test" } })

    const rqInput = screen.getByPlaceholderText(/enter a research question/i)
    fireEvent.change(rqInput, { target: { value: "RQ1" } })
    fireEvent.click(screen.getByRole("button", { name: /add/i }))
    fireEvent.click(screen.getByRole("button", { name: /next/i }))
    fireEvent.click(screen.getByRole("button", { name: /next/i }))

    // Should be on step 3
    await waitFor(() => {
      expect(screen.getByText(/rigor level/i)).toBeInTheDocument()
    })

    // Initially exploratory
    expect(screen.getByText(/minimal/i)).toBeInTheDocument()
    expect(screen.getByText(/warn/i)).toBeInTheDocument()
    expect(screen.getByText(/relaxed/i)).toBeInTheDocument()

    // Change to conservative
    const rigorSelect = screen.getAllByRole("combobox").find(
      (el) => el.getAttribute("aria-label")?.includes("rigor") || el.textContent?.includes("Rigor")
    ) || screen.getAllByRole("combobox")[0]
    
    if (rigorSelect) {
      fireEvent.click(rigorSelect)

      await waitFor(() => {
        const conservativeOption = screen.getByText(/conservative/i)
        fireEvent.click(conservativeOption)
      })
    }

    // Preview should update
    await waitFor(() => {
      expect(screen.getByText(/enforced/i)).toBeInTheDocument()
      expect(screen.getByText(/strict/i)).toBeInTheDocument()
    })
  })

  it("creates project and navigates on submit", async () => {
    render(<ProjectWizard />)

    // Fill all required fields
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: "Test Project" } })
    fireEvent.change(screen.getByLabelText(/thesis/i), { target: { value: "Test thesis" } })

    const rqInput = screen.getByPlaceholderText(/enter a research question/i)
    fireEvent.change(rqInput, { target: { value: "What is the impact?" } })
    fireEvent.click(screen.getByRole("button", { name: /add/i }))

    // Navigate through steps
    fireEvent.click(screen.getByRole("button", { name: /next/i }))
    fireEvent.click(screen.getByRole("button", { name: /next/i }))

    // Submit
    const createButton = await screen.findByRole("button", { name: /create project/i })
    fireEvent.click(createButton)

    await waitFor(() => {
      expect(mockCreateProject).toHaveBeenCalledWith({
        title: "Test Project",
        thesis: "Test thesis",
        research_questions: ["What is the impact?"],
        anti_scope: null,
        target_journal: null,
        seed_files: null,
      })
    })

    // Should navigate to project page
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/projects/test-project-id")
    })
  })
})

