/**
 * Tests for ClaimIdLink Component
 * Tests: click triggers highlight event, source pointer handling
 */

import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { ClaimIdLink } from "../claim-id-link"
import { EvidenceProvider, useEvidence } from "@/contexts/evidence-context"

describe("ClaimIdLink", () => {
  let highlightCallback: (coords: any) => void

  beforeEach(() => {
    highlightCallback = jest.fn()
  })

  it("renders claim ID as badge", () => {
    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="claim-123" />
      </EvidenceProvider>
    )

    expect(screen.getByText("claim-123")).toBeInTheDocument()
  })

  it("triggers highlight when clicked with source pointer", async () => {
    const sourcePointer = {
      doc_hash: "abc123",
      page: 5,
      bbox: [100, 200, 300, 400] as [number, number, number, number],
      snippet: "Evidence text",
    }

    // Create a test component that tracks highlights
    function HighlightTracker({ onHighlight }: { onHighlight: (coords: any) => void }) {
      const { highlight } = useEvidence()
      React.useEffect(() => {
        if (highlight) {
          onHighlight(highlight)
        }
      }, [highlight, onHighlight])
      return <ClaimIdLink claimId="claim-123" sourcePointer={sourcePointer} />
    }

    render(
      <EvidenceProvider>
        <HighlightTracker onHighlight={highlightCallback} />
      </EvidenceProvider>
    )

    const badge = screen.getByText("claim-123")
    fireEvent.click(badge)

    await waitFor(() => {
      expect(highlightCallback).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 5,
          bbox: {
            x1: 100,
            y1: 200,
            x2: 300,
            y2: 400,
          },
          doc_hash: "abc123",
          snippet: "Evidence text",
          claim_id: "claim-123",
        })
      )
    })
  })

  it("shows external link icon when source pointer is available", () => {
    const sourcePointer = {
      doc_hash: "abc123",
      page: 5,
      bbox: [100, 200, 300, 400] as [number, number, number, number],
    }

    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="claim-123" sourcePointer={sourcePointer} />
      </EvidenceProvider>
    )

    // Check for external link icon (lucide-react ExternalLink)
    const linkIcon = screen.getByText("claim-123").closest("div")?.querySelector("svg")
    expect(linkIcon).toBeInTheDocument()
  })

  it("handles click without source pointer gracefully", () => {
    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="claim-123" />
      </EvidenceProvider>
    )

    const badge = screen.getByText("claim-123")
    fireEvent.click(badge)

    // Should not call setHighlight without source pointer
    expect(mockSetHighlight).not.toHaveBeenCalled()
  })

  it("applies custom className and variant", () => {
    render(
      <EvidenceProvider>
        <ClaimIdLink claimId="claim-123" className="custom-class" variant="secondary" />
      </EvidenceProvider>
    )

    const badge = screen.getByText("claim-123")
    expect(badge).toHaveClass("custom-class")
  })
})

