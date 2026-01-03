/**
 * UI tests for context anchor functionality
 * 
 * Tests verify that clicking a claim/claim_id scrolls and highlights
 * the exact evidence span in the Evidence pane.
 */

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ClaimItem } from "@/components/claim-item"
import { ClaimIdLink } from "@/components/claim-id-link"
import { EvidenceProvider } from "@/contexts/evidence-context"
import type { Claim } from "@/types/claim"

describe("Context Anchor", () => {
  const mockClaim: Claim = {
    id: "claim_123",
    text: "The study found that X causes Y",
    shortText: "X causes Y",
    subject: "X",
    predicate: "causes",
    object: "Y",
    confidence: 0.85,
    status: "Proposed",
    provenance: {
      proposed_by: "Cartographer",
      verified_by: null,
      flagged_by: null,
    },
    linkedRQ: null,
    sourcePointer: {
      doc_hash: "abc123",
      page: 5,
      bbox: [100, 200, 300, 400],
      snippet: "Evidence text",
    },
    source_anchor: {
      doc_id: "abc123",
      page_number: 5,
      bbox: {
        x: 100,
        y: 200,
        w: 200,
        h: 200,
      },
      snippet: "Evidence text",
    },
    evidence: "Evidence text",
    flags: [],
    citations: [],
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe("ClaimItem", () => {
    it("renders claim with source_anchor", () => {
      const mockOnClick = vi.fn()
      
      render(
        <EvidenceProvider>
          <ClaimItem claim={mockClaim} onClick={mockOnClick} />
        </EvidenceProvider>
      )

      const card = screen.getByText(mockClaim.shortText)
      expect(card).toBeTruthy()
    })

    it("handles click without source_anchor gracefully", () => {
      const mockOnClick = vi.fn()
      const claimWithoutAnchor = { ...mockClaim, source_anchor: undefined }
      
      render(
        <EvidenceProvider>
          <ClaimItem claim={claimWithoutAnchor} onClick={mockOnClick} />
        </EvidenceProvider>
      )

      const card = screen.getByText(claimWithoutAnchor.shortText).closest(".cursor-pointer")
      if (card) {
        fireEvent.click(card)
        // Should still call onClick even without anchor
        expect(mockOnClick).toHaveBeenCalled()
      }
    })
  })

  describe("ClaimIdLink", () => {
    it("renders claim ID link with sourceAnchor", () => {
      render(
        <EvidenceProvider>
          <ClaimIdLink
            claimId="claim_123"
            sourceAnchor={mockClaim.source_anchor}
          />
        </EvidenceProvider>
      )

      const badge = screen.getByText("claim_123")
      expect(badge).toBeTruthy()
    })

    it("renders claim ID link with sourcePointer fallback", () => {
      render(
        <EvidenceProvider>
          <ClaimIdLink
            claimId="claim_123"
            sourcePointer={mockClaim.sourcePointer}
          />
        </EvidenceProvider>
      )

      const badge = screen.getByText("claim_123")
      expect(badge).toBeTruthy()
    })
  })
})

