//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useMemo } from "react"
import Link from "next/link"
import { usePathname, useSearchParams, useRouter } from "next/navigation"
import { FileText, Network } from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { useProjectStore } from "@/state/useProjectStore"
import { toast } from "@/hooks/use-toast"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Badge } from "@/components/ui/badge"

export function AppSidebar() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const router = useRouter()
  const { activeProject, activeProjectId, activeJobId, activePdfUrl } = useProjectStore()

  // Extract job context from URL if on workbench page
  const workbenchJobId = useMemo(() => {
    if (pathname === "/research-workbench") {
      return searchParams.get("jobId") || null
    }
    return null
  }, [pathname, searchParams])

  const workbenchProjectId = useMemo(() => {
    if (pathname === "/research-workbench") {
      return searchParams.get("projectId") || null
    }
    return null
  }, [pathname, searchParams])

  const workbenchPdfUrl = useMemo(() => {
    if (pathname === "/research-workbench") {
      return searchParams.get("pdfUrl") || null
    }
    return null
  }, [pathname, searchParams])

  // Construct workbench URL if we have context (prefer URL/store)
  const workbenchUrl = useMemo(() => {
    // Prefer URL params if on workbench page
    if (workbenchJobId && workbenchProjectId) {
      let url = `/research-workbench?jobId=${workbenchJobId}&projectId=${workbenchProjectId}`
      if (workbenchPdfUrl) {
        url += `&pdfUrl=${encodeURIComponent(workbenchPdfUrl)}`
      }
      return url
    }
    if (activeJobId && activeProjectId) {
      let url = `/research-workbench?jobId=${activeJobId}&projectId=${activeProjectId}`
      if (activePdfUrl) {
        url += `&pdfUrl=${encodeURIComponent(activePdfUrl)}`
      }
      return url
    }
    return null
  }, [workbenchJobId, workbenchProjectId, workbenchPdfUrl, activeJobId, activeProjectId, activePdfUrl])

  // Handle workbench navigation - context-aware
  const handleWorkbenchClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault()
    router.push("/projects")
    toast({
      title: "Select a project or job",
      description: "Select a project/job to open the Workbench.",
      variant: "default",
    })
  }

  type NavItem = {
    title: string
    icon: React.ComponentType<{ className?: string }>
    href: string
  } | {
    title: string
    icon: React.ComponentType<{ className?: string }>
    href: string
    onClick: (e: React.MouseEvent<HTMLButtonElement>) => void
  }

  const navigationItems: NavItem[] = [
    {
      title: "Projects",
      icon: FileText,
      href: "/projects",
    },
    workbenchUrl
      ? {
          title: "Research Workbench",
          icon: Network,
          href: workbenchUrl,
        }
      : {
          title: "Research Workbench",
          icon: Network,
          href: "#",
          onClick: handleWorkbenchClick,
        },
  ]

  // Determine current project/job for context display
  const currentProjectId = activeProjectId || workbenchProjectId
  const currentProjectName = activeProject?.title || null
  const currentJobId = workbenchJobId || activeJobId || null

  return (
    <Sidebar>
      <SidebarContent>
        {/* Active Context Indicator */}
        {(currentProjectId || currentJobId) && (
          <>
            <SidebarHeader className="pb-2">
              <SidebarGroupLabel>Context</SidebarGroupLabel>
              <div className="space-y-1 px-2 text-xs">
                {currentProjectName && (
                  <div className="flex items-center gap-2 text-sidebar-foreground/70">
                    <FileText className="h-3 w-3" />
                    <span className="truncate font-medium">{currentProjectName}</span>
                    <Badge variant="secondary" className="h-5 px-2 animate-pulse">
                      Active
                    </Badge>
                  </div>
                )}
                {currentJobId && (
                  <div className="flex items-center gap-2 text-sidebar-foreground/60">
                    <Network className="h-3 w-3" />
                    <span className="truncate font-mono text-[10px]">
                      Job: {currentJobId.substring(0, 8)}...
                    </span>
                  </div>
                )}
              </div>
            </SidebarHeader>
            <SidebarSeparator />
          </>
        )}

        {/* Navigation Items */}
        <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {navigationItems.map((item, index) => {
                  const baseHref = item.href.split("?")[0]
                  const isActive = pathname === baseHref || pathname?.startsWith(baseHref + "/")

                  return (
                    <SidebarMenuItem key={`${item.href}-${index}`}>
                      {"onClick" in item ? (
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <SidebarMenuButton
                                onClick={item.onClick}
                                isActive={pathname === "/research-workbench"}
                                className="cursor-not-allowed opacity-60"
                                aria-disabled
                              >
                                <item.icon />
                                <span>{item.title}</span>
                              </SidebarMenuButton>
                            </TooltipTrigger>
                            <TooltipContent>
                              Select a project/job to open workbench.
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      ) : (
                        <SidebarMenuButton asChild isActive={isActive}>
                          <Link href={item.href}>
                            <item.icon />
                            <span>{item.title}</span>
                          </Link>
                        </SidebarMenuButton>
                      )}
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
