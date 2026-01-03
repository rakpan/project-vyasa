/**
 * Tests for ClaimItem Component
 * Tests: breadcrumb display, status badges, RQ linking
 */

import { render, screen, fireEvent } from "@testing-library/react"
import { ClaimItem } from "../claim-item"
import type { Claim } from "@/types/claim"

const mockClaim: Claim = {
  id: "claim-1",
  text: "Subject predicate Object",
  shortText: "Subject → Object",
  subject: "Subject",
  predicate: "predicate",
  object: "Object",
  confidence: 0.85,
  status: "Accepted",
  provenance: {
    proposed_by: "Cartographer",
    verified_by: "Brain",
    flagged_by: null,
  },
  linkedRQ: "What is the impact?",
  sourcePointer: {
    doc_hash: "abc123",
    page: 1,
    snippet: "Evidence text",
  },
  evidence: "Evidence text",
  flags: [],
  citations: [],
}

describe("ClaimItem", () => {
  it("renders claim text and status badge", () => {
    const onClick = jest.fn()
    render(<ClaimItem claim={mockClaim} onClick={onClick} />)

    expect(screen.getByText("Subject → Object")).toBeInTheDocument()
    expect(screen.getByText("Accepted")).toBeInTheDocument()
  })

  it("displays provenance breadcrumb", () => {
    const onClick = jest.fn()
    render(<ClaimItem claim={mockClaim} onClick={onClick} />)

    expect(screen.getByText(/Proposed by: Cartographer/)).toBeInTheDocument()
    expect(screen.getByText(/Verified by: Brain/)).toBeInTheDocument()
  })

  it("displays linked RQ badge", () => {
    const onClick = jest.fn()
    render(<ClaimItem claim={mockClaim} onClick={onClick} />)

    expect(screen.getByText(/RQ:/)).toBeInTheDocument()
  })

  it("displays confidence badge", () => {
    const onClick = jest.fn()
    render(<ClaimItem claim={mockClaim} onClick={onClick} />)

    expect(screen.getByText("85%")).toBeInTheDocument()
  })

  it("displays flags when present", () => {
    const claimWithFlags: Claim = {
      ...mockClaim,
      flags: ["Conflict detected", "Low confidence"],
    }
    const onClick = jest.fn()
    render(<ClaimItem claim={claimWithFlags} onClick={onClick} />)

    expect(screen.getByText(/2 flags/)).toBeInTheDocument()
  })

  it("calls onClick when clicked", () => {
    const onClick = jest.fn()
    render(<ClaimItem claim={mockClaim} onClick={onClick} />)

    fireEvent.click(screen.getByText("Subject → Object").closest("div")!)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("applies correct styling for Flagged status", () => {
    const flaggedClaim: Claim = {
      ...mockClaim,
      status: "Flagged",
    }
    const onClick = jest.fn()
    const { container } = render(<ClaimItem claim={flaggedClaim} onClick={onClick} />)

    const card = container.querySelector(".border-red-300")
    expect(card).toBeInTheDocument()
  })
})

