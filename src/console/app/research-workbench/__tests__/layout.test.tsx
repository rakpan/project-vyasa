import { render, screen } from "@testing-library/react"
import React from "react"
import { vi } from "vitest"
import type { URLSearchParams as URLSearchParamsType } from "url"

vi.mock("@/components/ZenSourceVault", () => ({
  ZenSourceVault: ({ fileUrl }: any) => <div data-testid="zen-source" data-url={fileUrl} />,
}))
vi.mock("@/components/LiveGraphWorkbench", () => ({
  LiveGraphWorkbench: () => <div data-testid="live-graph" />,
}))
vi.mock("@/components/ZenManuscriptEditor", () => ({
  ZenManuscriptEditor: () => <div data-testid="manuscript" />,
}))
vi.mock("@/hooks/use-toast", () => ({ toast: vi.fn() }))
let searchParams: URLSearchParamsType = new URLSearchParams()
const pushMock = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => searchParams,
}))
vi.mock("@/state/useProjectStore", () => ({
  useProjectStore: () => ({
    activeProjectId: "proj-1",
    setActiveProject: vi.fn(),
    setActiveJobContext: vi.fn(),
  }),
}))
vi.mock("@/state/useResearchStore", () => ({
  useResearchStore: () => ({
    focusMode: false,
    toggleFocusMode: vi.fn(),
  }),
}))

import WorkbenchPage from "../page"

describe("Research Workbench layout", () => {
  it("redirects when jobId/projectId missing", () => {
    searchParams = new URLSearchParams()
    render(<WorkbenchPage />)
    expect(screen.queryByTestId("zen-source")).not.toBeInTheDocument()
  })

  it("renders source panel when pdfUrl provided", () => {
    searchParams = new URLSearchParams({
      jobId: "job-1",
      projectId: "proj-1",
      pdfUrl: "https://example.com/doc.pdf",
    })
    render(<WorkbenchPage />)
    expect(screen.getByTestId("zen-source")).toBeInTheDocument()
  })
})
