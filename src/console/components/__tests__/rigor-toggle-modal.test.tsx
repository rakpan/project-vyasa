/**
 * Tests for RigorToggleModal Component
 * Tests: modal opens/closes, rigor selection, API call, warning display
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { RigorToggleModal } from "../rigor-toggle-modal"

// Mock fetch
global.fetch = jest.fn()

describe("RigorToggleModal", () => {
  const mockOnRigorChanged = jest.fn()
  const mockOnClose = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    ;(global.fetch as jest.Mock).mockClear()
  })

  it("renders modal when open", () => {
    render(
      <RigorToggleModal
        open={true}
        onClose={mockOnClose}
        currentRigor="exploratory"
        projectId="project_123"
      />
    )

    expect(screen.getByText("Change Rigor Level")).toBeInTheDocument()
    expect(screen.getByText("exploratory")).toBeInTheDocument()
  })

  it("does not render when closed", () => {
    render(
      <RigorToggleModal
        open={false}
        onClose={mockOnClose}
        currentRigor="exploratory"
        projectId="project_123"
      />
    )

    expect(screen.queryByText("Change Rigor Level")).not.toBeInTheDocument()
  })

  it("displays current rigor level", () => {
    render(
      <RigorToggleModal
        open={true}
        onClose={mockOnClose}
        currentRigor="conservative"
        projectId="project_123"
      />
    )

    expect(screen.getByText("conservative")).toBeInTheDocument()
  })

  it("allows selecting different rigor level", () => {
    render(
      <RigorToggleModal
        open={true}
        onClose={mockOnClose}
        currentRigor="exploratory"
        projectId="project_123"
      />
    )

    const conservativeRadio = screen.getByLabelText(/Conservative/i)
    fireEvent.click(conservativeRadio)

    expect(conservativeRadio).toBeChecked()
  })

  it("calls API when saving", async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ project_id: "project_123", rigor_level: "conservative" }),
    })

    render(
      <RigorToggleModal
        open={true}
        onClose={mockOnClose}
        currentRigor="exploratory"
        projectId="project_123"
        onRigorChanged={mockOnRigorChanged}
      />
    )

    const conservativeRadio = screen.getByLabelText(/Conservative/i)
    fireEvent.click(conservativeRadio)

    const saveButton = screen.getByText("Save Changes")
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/proxy/orchestrator/api/projects/project_123/rigor",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rigor_level: "conservative" }),
        }
      )
    })

    await waitFor(() => {
      expect(mockOnRigorChanged).toHaveBeenCalledWith("conservative")
      expect(mockOnClose).toHaveBeenCalled()
    })
  })

  it("shows warning about future jobs only", () => {
    render(
      <RigorToggleModal
        open={true}
        onClose={mockOnClose}
        currentRigor="exploratory"
        projectId="project_123"
      />
    )

    expect(screen.getByText(/future jobs/i)).toBeInTheDocument()
    expect(screen.getByText(/currently running/i)).toBeInTheDocument()
  })

  it("disables save button when same rigor is selected", () => {
    render(
      <RigorToggleModal
        open={true}
        onClose={mockOnClose}
        currentRigor="exploratory"
        projectId="project_123"
      />
    )

    const saveButton = screen.getByText("Save Changes")
    expect(saveButton).toBeDisabled()
  })

  it("handles API errors gracefully", async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: "Failed to update" }),
    })

    render(
      <RigorToggleModal
        open={true}
        onClose={mockOnClose}
        currentRigor="exploratory"
        projectId="project_123"
      />
    )

    const conservativeRadio = screen.getByLabelText(/Conservative/i)
    fireEvent.click(conservativeRadio)

    const saveButton = screen.getByText("Save Changes")
    fireEvent.click(saveButton)

    await waitFor(() => {
      // Modal should remain open on error
      expect(screen.getByText("Change Rigor Level")).toBeInTheDocument()
    })
  })
})

