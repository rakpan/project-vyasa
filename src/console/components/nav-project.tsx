//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { useProjectStore } from "@/state/useProjectStore"
import { FileText, Network, BookOpen, Folder, LayoutGrid } from "lucide-react"
import { cn } from "@/lib/utils"
import { useMemo } from "react"

/**
 * Project Sub-Navigation - Renders only when activeProjectId is set
 * Shows project-specific navigation links
 */
export function NavProject() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { activeProjectId, activeProject } = useProjectStore()

  // Construct Research Cockpit URL - only show when job context exists
  // Research Cockpit is now job-only; project details are in Project Profile
  const researchCockpitUrl = useMemo(() => {
    if (!activeProjectId) return ""
    
    // Only show Research Cockpit link if we're currently on a job-driven page
    // (i.e., we have jobId in the URL)
    const isCurrentlyOnJobDrivenPage = pathname === "/research-workbench"
    if (isCurrentlyOnJobDrivenPage) {
      const jobId = searchParams.get("jobId")
      const pdfUrl = searchParams.get("pdfUrl")
      if (jobId) {
        let url = `/research-workbench?jobId=${jobId}&projectId=${activeProjectId}`
        if (pdfUrl) {
          url += `&pdfUrl=${encodeURIComponent(pdfUrl)}`
        }
        return url
      }
    }
    // No job context - don't show Research Cockpit link
    return ""
  }, [activeProjectId, pathname, searchParams])

  // Don't render if no active project (after all hooks)
  if (!activeProjectId) {
    return null
  }

  const projectNavItems = [
    {
      title: "Project Profile",
      href: `/projects/${activeProjectId}/profile`,
      icon: Folder,
      isActive: pathname === `/projects/${activeProjectId}/profile`,
    },
    {
      title: "Evidence Engine",
      href: `/projects/${activeProjectId}`,
      icon: Network,
      isActive: pathname === `/projects/${activeProjectId}`,
    },
    {
      title: "Workbench",
      href: `/projects/${activeProjectId}/workbench`,
      icon: LayoutGrid,
      isActive: pathname === `/projects/${activeProjectId}/workbench`,
    },
    {
      title: "Manuscript",
      href: `/projects/${activeProjectId}/manuscript`,
      icon: BookOpen,
      isActive: pathname === `/projects/${activeProjectId}/manuscript`,
    },
    // Only show Research Cockpit when job context exists
    ...(researchCockpitUrl ? [{
      title: "Research Cockpit",
      href: researchCockpitUrl,
      icon: FileText,
      isActive: pathname === "/research-workbench",
    }] : []),
  ]

  return (
    <aside className="fixed left-[72px] top-0 h-screen w-[200px] bg-white border-r border-slate-200 flex flex-col z-30">
      {/* Section Header */}
      <div className="px-4 py-3 border-b border-slate-200">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          SUB-NAVIGATION
        </div>
        {activeProject?.title && (
          <div className="mt-1 text-xs font-medium text-foreground truncate" title={activeProject.title}>
            {activeProject.title}
          </div>
        )}
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 py-2">
        {projectNavItems.map((item) => {
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 px-4 py-2 text-xs text-[#111827] transition-colors",
                "hover:bg-slate-50",
                item.isActive && "bg-white shadow-[inset_2px_0_0_#111827] font-medium"
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span>{item.title}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}

