//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { useEffect, useMemo } from "react"
import { ChevronRight, Home } from "lucide-react"
import { useProjectStore } from "@/state/useProjectStore"
import { ThemeToggle } from "@/components/theme-toggle"
import { LogoutButton } from "@/components/logout-button"
import { cn } from "@/lib/utils"

/**
 * Breadcrumbs & Header Actions - Persistent global header
 * Synchronized with URL parameters and project store state
 * Auto-restores state from URL on page reload
 */
export function TopBar() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { activeProject, activeProjectId, activeJobId, setActiveProject, setActiveJobContext } = useProjectStore()

  // Extract URL parameters for auto-restore
  const urlProjectId = useMemo(() => searchParams.get("projectId") || "", [searchParams])
  const urlJobId = useMemo(() => searchParams.get("jobId") || "", [searchParams])
  const urlThreadId = useMemo(() => searchParams.get("threadId") || "", [searchParams])
  const urlPdfUrl = useMemo(() => searchParams.get("pdfUrl") || "", [searchParams])

  // Auto-restore state from URL parameters on page reload
  useEffect(() => {
    if (urlProjectId && urlProjectId !== activeProjectId) {
      setActiveProject(urlProjectId).catch((error) => {
        console.error("Failed to restore project from URL:", error)
      })
    }
    if (urlProjectId && urlJobId) {
      setActiveJobContext(urlJobId, urlProjectId, urlPdfUrl || null, urlThreadId || urlJobId)
    }
  }, [urlProjectId, urlJobId, urlThreadId, urlPdfUrl, activeProjectId, setActiveProject, setActiveJobContext])

  // Determine active pane from pathname
  const activePane = useMemo(() => {
    if (pathname === "/research-workbench") return "Workbench"
    if (pathname.includes("/manuscript")) return "Manuscript"
    if (pathname.match(/^\/projects\/[^/]+$/)) return "Evidence Engine"
    return null
  }, [pathname])

  // Build breadcrumbs synchronized with URL and store state
  const breadcrumbs = useMemo(() => {
    const crumbs: Array<{ label: string; href?: string }> = [
      { label: "Projects", href: "/projects" },
    ]

    // Add project name if available (from store or URL)
    if (activeProjectId) {
      const projectName = activeProject?.title || "Project"
      crumbs.push({
        label: projectName,
        href: `/projects/${activeProjectId}`,
      })
    }

    // Add active pane if available
    if (activePane) {
      crumbs.push({ label: activePane })
    }

    return crumbs
  }, [activeProjectId, activeProject, activePane])

  return (
    <header className="sticky top-0 z-50 h-12 border-b border-slate-200 bg-white flex items-center justify-between px-4">
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-1.5 text-sm text-foreground" aria-label="Breadcrumb">
        <Link
          href="/projects"
          className="flex items-center gap-1 hover:text-muted-foreground transition-colors"
          aria-label="Projects"
        >
          <Home className="h-3.5 w-3.5" />
        </Link>
        {breadcrumbs.map((crumb, index) => (
          <div key={index} className="flex items-center gap-1.5">
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            {crumb.href ? (
              <Link
                href={crumb.href}
                className="hover:text-muted-foreground transition-colors"
              >
                {crumb.label}
              </Link>
            ) : (
              <span className="font-medium" aria-current="page">{crumb.label}</span>
            )}
          </div>
        ))}
      </nav>

      {/* Global Actions - Right-aligned */}
      <div className="flex items-center gap-2">
        <LogoutButton />
        <ThemeToggle />
      </div>
    </header>
  )
}
