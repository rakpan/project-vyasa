import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { StrategicInterventionPanel } from "../StrategicInterventionPanel"
import { vi } from "vitest"
import { useRouter } from "next/navigation"

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

const mockFetch = vi.fn()
global.fetch = mockFetch as any

const proposal = {
  proposal_id: "p1",
  conflict_summary: "summary",
  conflict_hash: "hash123456",
  pivot_type: "SCOPE",
  proposed_pivot: "new thesis",
  architectural_rationale: "rationale",
  evidence_anchors: ["c1"],
  what_stays_true: ["keep"],
}

describe("StrategicInterventionPanel", () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it("loads proposal on mount", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ proposal }),
    })
    render(<StrategicInterventionPanel jobId="j1" projectId="p1" />)
    await waitFor(() => expect(mockFetch).toHaveBeenCalled())
    expect(await screen.findByText("summary")).toBeInTheDocument()
  })

  it("submits accept with edited pivot", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ proposal }) }) // GET
      .mockResolvedValueOnce({ ok: true, json: async () => ({ new_job_id: "newJob" }) }) // POST
    render(<StrategicInterventionPanel jobId="j1" projectId="p1" />)
    await screen.findByDisplayValue("new thesis")
    const textarea = screen.getByRole("textbox")
    fireEvent.change(textarea, { target: { value: "edited pivot" } })
    const acceptBtn = screen.getByText(/Accept & Restart Analysis/)
    fireEvent.click(acceptBtn)
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2))
    const body = JSON.parse(mockFetch.mock.calls[1][1].body)
    expect(body.action).toBe("accept")
    expect(body.edited_pivot).toBe("edited pivot")
  })

  it("submits reject", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ proposal }) }) // GET
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) }) // POST
    render(<StrategicInterventionPanel jobId="j1" projectId="p1" />)
    await screen.findByText("summary")
    const rejectBtn = screen.getByText(/Reject Reframe/)
    fireEvent.click(rejectBtn)
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2))
    const body = JSON.parse(mockFetch.mock.calls[1][1].body)
    expect(body.action).toBe("reject")
  })

  it("disables buttons while submitting", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ proposal }) })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ new_job_id: "newJob" }),
      })
    render(<StrategicInterventionPanel jobId="j1" projectId="p1" />)
    await screen.findByText("summary")
    const acceptBtn = screen.getByText(/Accept & Restart Analysis/)
    fireEvent.click(acceptBtn)
    expect(acceptBtn).toBeDisabled()
  })
})
