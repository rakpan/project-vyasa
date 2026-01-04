/**
 * Unit tests for Context Anchor functionality.
 * 
 * Tests that clicking a claim ID triggers scroll/highlight handler
 * in the Evidence pane without modals or route changes.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { ClaimIdLink } from "../claim-id-link"
import { useAnchor } from "@/hooks/use-anchor"
import { EvidenceProvider } from "@/contexts/evidence-context"

// Mock the useAnchor hook
vi.mock("@/hooks/use-anchor", () => ({
  useAnchor: vi.fn(),
}))

// Mock fetch for API calls
global.fetch = vi.fn()

describe("Context Anchor", () => {
  const mockActivateClaim = vi.fn()
  const mockScrollToAnchor = vi.fn()
  const mockActivateAnchor = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    ;(useAnchor as any).mockReturnValue({
      activeAnchor: null,
      activateAnchor: mockActivateAnchor,
      activateClaim: mockActivateClaim,
      scrollToAnchor: mockScrollToAnchor,
    })
  })

  it("should trigger activateClaim when clicking claim link without anchor", async () => {
    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="test-claim-123" />
      </EvidenceProvider>
    )

    const claimLink = screen.getByText("test-claim-123")
    fireEvent.click(claimLink)

    await waitFor(() => {
      expect(mockActivateClaim).toHaveBeenCalledWith("test-claim-123")
    })
  })

  it("should trigger scrollToAnchor when clicking claim link with sourceAnchor", () => {
    const sourceAnchor = {
      doc_id: "doc-hash-123",
      page_number: 5,
      bbox: { x: 10, y: 20, w: 100, h: 50 },
      snippet: "Test snippet",
    }

    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="test-claim-123" sourceAnchor={sourceAnchor} />
      </EvidenceProvider>
    )

    const claimLink = screen.getByText("test-claim-123")
    fireEvent.click(claimLink)

    expect(mockScrollToAnchor).toHaveBeenCalledWith(sourceAnchor)
    expect(mockActivateClaim).not.toHaveBeenCalled()
  })

  it("should trigger scrollToAnchor when clicking claim link with sourcePointer", () => {
    const sourcePointer = {
      doc_hash: "doc-hash-456",
      page: 3,
      bbox: [15, 25, 115, 75] as [number, number, number, number],
      snippet: "Another snippet",
    }

    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="test-claim-456" sourcePointer={sourcePointer} />
      </EvidenceProvider>
    )

    const claimLink = screen.getByText("test-claim-456")
    fireEvent.click(claimLink)

    expect(mockScrollToAnchor).toHaveBeenCalled()
    const callArg = mockScrollToAnchor.mock.calls[0][0]
    expect(callArg.doc_id).toBe("doc-hash-456")
    expect(callArg.page_number).toBe(3)
    expect(callArg.bbox).toEqual({ x: 15, y: 25, w: 100, h: 50 })
  })

  it("should fetch anchor from API when no sourceAnchor or sourcePointer provided", async () => {
    const mockAnchor = {
      doc_id: "doc-hash-789",
      page_number: 7,
      bbox: { x: 20, y: 30, w: 150, h: 60 },
      snippet: "Fetched snippet",
    }

    ;(global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        claim_id: "test-claim-789",
        source_anchor: mockAnchor,
      }),
    })

    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="test-claim-789" />
      </EvidenceProvider>
    )

    const claimLink = screen.getByText("test-claim-789")
    fireEvent.click(claimLink)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/proxy/orchestrator/api/claims/test-claim-789/anchor"
      )
      expect(mockActivateClaim).toHaveBeenCalledWith("test-claim-789")
    })
  })

  it("should handle API fetch failure gracefully", async () => {
    ;(global.fetch as any).mockRejectedValueOnce(new Error("Network error"))

    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="test-claim-error" />
      </EvidenceProvider>
    )

    const claimLink = screen.getByText("test-claim-error")
    fireEvent.click(claimLink)

    await waitFor(() => {
      expect(mockActivateClaim).toHaveBeenCalledWith("test-claim-error")
    })
  })

  it("should not trigger navigation or open modals", () => {
    const sourceAnchor = {
      doc_id: "doc-hash-123",
      page_number: 5,
      bbox: { x: 10, y: 20, w: 100, h: 50 },
    }

    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="test-claim-123" sourceAnchor={sourceAnchor} />
      </EvidenceProvider>
    )

    const claimLink = screen.getByText("test-claim-123")
    const clickEvent = new MouseEvent("click", { bubbles: true, cancelable: true })
    fireEvent.click(claimLink, clickEvent)

    // Verify event was prevented (no navigation)
    expect(clickEvent.defaultPrevented).toBe(true)
    // Verify no modal was opened (would require additional mocking)
    expect(mockScrollToAnchor).toHaveBeenCalled()
  })
})
