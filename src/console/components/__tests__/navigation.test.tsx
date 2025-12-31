import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import React from "react"
import { vi } from "vitest"

vi.mock("next/navigation", () => {
  const push = vi.fn()
  const redirect = vi.fn()
  const useRouter = () => ({ push })
  const usePathname = () => "/"
  const useSearchParams = () => new URLSearchParams()
  return { useRouter, usePathname, useSearchParams, redirect }
})

vi.mock("@/hooks/use-toast", () => ({
  toast: vi.fn(),
}))

vi.mock("@/state/useProjectStore", () => ({
  useProjectStore: () => ({
    activeProject: null,
    activeProjectId: null,
    activeJobId: null,
    activePdfUrl: null,
  }),
}))

vi.mock("@/components/ui/sidebar", () => {
  const Actual = vi.importActual("@/components/ui/sidebar") as any
  return {
    ...Actual,
    Sidebar: ({ children }: any) => <div data-testid="sidebar">{children}</div>,
  }
})

import Home from "@/app/page"
import { AppSidebar } from "@/components/app-sidebar"
import { useRouter, redirect } from "next/navigation"

describe("Navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("redirects / to /projects", () => {
    Home()
    expect(redirect).toHaveBeenCalledWith("/projects")
  })

  it("sidebar workbench click without context redirects to projects and toasts", async () => {
    const router = useRouter()
    render(<AppSidebar />)
    const btn = screen.getByText("Research Workbench")
    fireEvent.click(btn)
    expect(router.push).toHaveBeenCalledWith("/projects")
  })
})
