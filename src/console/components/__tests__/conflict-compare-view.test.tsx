/**
 * Tests for ConflictCompareView Component
 * Tests: side-by-side rendering, source excerpts, page references
 */

import { render, screen } from "@testing-library/react"
import { ConflictCompareView } from "../conflict-compare-view"
import type { SourcePointer } from "@/types/claim"

const mockSourceA: SourcePointer = {
  doc_hash: "abc123def456",
  page: 5,
  snippet: "Source A asserts that X is true based on experimental evidence.",
  bbox: [100, 200, 300, 400],
}

const mockSourceB: SourcePointer = {
  doc_hash: "xyz789ghi012",
  page: 12,
  snippet: "Source B contradicts this, stating that X is false due to methodological concerns.",
  bbox: [50, 150, 250, 350],
}

describe("ConflictCompareView", () => {
  it("renders side-by-side source comparison", () => {
    render(
      <ConflictCompareView
        sourceA={{ sourcePointer: mockSourceA, label: "Source A" }}
        sourceB={{ sourcePointer: mockSourceB, label: "Source B" }}
        conflictExplanation="Source A asserts X, while Source B contradicts this on page 12."
      />
    )

    expect(screen.getByText("Source A")).toBeInTheDocument()
    expect(screen.getByText("Source B")).toBeInTheDocument()
    expect(screen.getByText("Page 5")).toBeInTheDocument()
    expect(screen.getByText("Page 12")).toBeInTheDocument()
  })

  it("displays conflict explanation", () => {
    render(
      <ConflictCompareView
        sourceA={{ sourcePointer: mockSourceA }}
        sourceB={{ sourcePointer: mockSourceB }}
        conflictExplanation="Source A asserts X, while Source B contradicts this on page 12."
      />
    )

    expect(screen.getByText(/Source A asserts X/)).toBeInTheDocument()
  })

  it("displays source excerpts", () => {
    render(
      <ConflictCompareView
        sourceA={{ sourcePointer: mockSourceA }}
        sourceB={{ sourcePointer: mockSourceB }}
      />
    )

    expect(screen.getByText(/Source A asserts that X is true/)).toBeInTheDocument()
    expect(screen.getByText(/Source B contradicts this/)).toBeInTheDocument()
  })

  it("displays claim text when provided", () => {
    render(
      <ConflictCompareView
        sourceA={{ sourcePointer: mockSourceA, claimText: "Claim A: X is true" }}
        sourceB={{ sourcePointer: mockSourceB, claimText: "Claim B: X is false" }}
      />
    )

    expect(screen.getByText("Claim A: X is true")).toBeInTheDocument()
    expect(screen.getByText("Claim B: X is false")).toBeInTheDocument()
  })

  it("handles missing snippets gracefully", () => {
    const sourceWithoutSnippet: SourcePointer = {
      doc_hash: "abc123",
      page: 1,
    }

    render(
      <ConflictCompareView
        sourceA={{ sourcePointer: sourceWithoutSnippet }}
        sourceB={{ sourcePointer: mockSourceB }}
      />
    )

    expect(screen.getByText(/No excerpt available/)).toBeInTheDocument()
  })

  it("displays document hash when page is missing", () => {
    const sourceWithoutPage: SourcePointer = {
      doc_hash: "abc123def456",
      snippet: "Some text",
    }

    render(
      <ConflictCompareView
        sourceA={{ sourcePointer: sourceWithoutPage }}
        sourceB={{ sourcePointer: mockSourceB }}
      />
    )

    expect(screen.getByText(/Doc: abc123def4/)).toBeInTheDocument()
  })
})

