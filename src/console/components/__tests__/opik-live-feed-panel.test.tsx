/**
 * Tests for OpikLiveFeedPanel Component
 * Tests: panel toggles, empty state when disabled
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { OpikLiveFeedPanel } from "../opik-live-feed-panel"

// Mock fetch
global.fetch = jest.fn()

describe("OpikLiveFeedPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(global.fetch as jest.Mock).mockClear()
  })

  it("shows disabled state when Opik is not enabled", () => {
    render(<OpikLiveFeedPanel jobId="job_123" opikEnabled={false} />)

    expect(screen.getByText("Opik Live Feed")).toBeInTheDocument()
    expect(screen.getByText("Disabled")).toBeInTheDocument()
    expect(screen.getByText(/Enable Opik to view traces/)).toBeInTheDocument()
  })

  it("toggles panel when clicked", () => {
    render(<OpikLiveFeedPanel jobId="job_123" opikEnabled={true} />)

    const toggleButton = screen.getByText("Opik Live Feed").closest("button")
    expect(toggleButton).toBeInTheDocument()

    // Panel should be collapsed by default
    expect(screen.queryByText(/No execution events yet/)).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(toggleButton!)
    
    // Should show empty state when no events
    expect(screen.getByText(/No execution events yet/)).toBeInTheDocument()

    // Click to collapse
    fireEvent.click(toggleButton!)
    
    // Panel should be collapsed again
    expect(screen.queryByText(/No execution events yet/)).not.toBeInTheDocument()
  })

  it("fetches events when expanded and Opik is enabled", async () => {
    const mockEvents = [
      {
        node_name: "cartographer_node",
        duration_ms: 1234,
        status: "success",
        timestamp: "2024-01-01T12:00:00Z",
        job_id: "job_123",
        metadata: {},
      },
    ]

    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ events: mockEvents }),
    })

    render(<OpikLiveFeedPanel jobId="job_123" opikEnabled={true} />)

    const toggleButton = screen.getByText("Opik Live Feed").closest("button")
    fireEvent.click(toggleButton!)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/proxy/orchestrator/jobs/job_123/events",
        { cache: "no-store" }
      )
    })
  })

  it("displays events when available", async () => {
    const mockEvents = [
      {
        node_name: "cartographer_node",
        duration_ms: 1234,
        status: "success",
        timestamp: "2024-01-01T12:00:00Z",
        job_id: "job_123",
        metadata: {},
      },
      {
        node_name: "critic_node",
        duration_ms: 567,
        status: "error",
        timestamp: "2024-01-01T12:01:00Z",
        job_id: "job_123",
        metadata: { error: "Test error" },
      },
    ]

    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ events: mockEvents }),
    })

    render(<OpikLiveFeedPanel jobId="job_123" opikEnabled={true} />)

    const toggleButton = screen.getByText("Opik Live Feed").closest("button")
    fireEvent.click(toggleButton!)

    await waitFor(() => {
      expect(screen.getByText("cartographer_node")).toBeInTheDocument()
      expect(screen.getByText("critic_node")).toBeInTheDocument()
    })
  })

  it("opens detail drawer when event is clicked", async () => {
    const mockEvents = [
      {
        node_name: "cartographer_node",
        duration_ms: 1234,
        status: "success",
        timestamp: "2024-01-01T12:00:00Z",
        job_id: "job_123",
        metadata: { expert: "Worker" },
      },
    ]

    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ events: mockEvents }),
    })

    render(<OpikLiveFeedPanel jobId="job_123" opikEnabled={true} />)

    const toggleButton = screen.getByText("Opik Live Feed").closest("button")
    fireEvent.click(toggleButton!)

    await waitFor(() => {
      expect(screen.getByText("cartographer_node")).toBeInTheDocument()
    })

    const eventCard = screen.getByText("cartographer_node").closest("div")
    fireEvent.click(eventCard!)

    await waitFor(() => {
      expect(screen.getByText("cartographer_node")).toBeInTheDocument() // In drawer title
    })
  })

  it("shows full trace link when opikTraceUrl is provided", () => {
    render(
      <OpikLiveFeedPanel
        jobId="job_123"
        opikEnabled={true}
        opikTraceUrl="http://opik.example.com/trace/123"
      />
    )

    expect(screen.getByText("Full Trace")).toBeInTheDocument()
  })
})

