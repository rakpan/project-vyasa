//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useMemo } from "react"
import Link from "next/link"
import { usePathname, useSearchParams, useRouter } from "next/navigation"
import { FileText, Network, FolderKanban, Activity } from "lucide-react"
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
import { cn } from "@/lib/utils"

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
    <Sidebar collapsible="icon" className="border-r border-border">
      <SidebarContent>
        {/* Active Project Context - High Density */}
        <SidebarHeader className="px-2 py-1.5">
          <SidebarGroupLabel className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground group-data-[collapsible=icon]:hidden">
            Active Project
          </SidebarGroupLabel>
          {currentProjectName ? (
            <div className="mt-1 space-y-0.5">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded group-data-[collapsible=icon]:justify-center">
                      <FolderKanban className="h-3.5 w-3.5 text-foreground/70 shrink-0" />
                      <span className="text-[12px] font-medium text-foreground truncate group-data-[collapsible=icon]:hidden">
                        {currentProjectName}
                      </span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="group-data-[collapsible=icon]:block hidden">
                    <div className="text-xs">
                      <div className="font-semibold">{currentProjectName}</div>
                      {currentJobId && (
                        <div className="text-muted-foreground mt-0.5">
                          Job: {currentJobId.substring(0, 8)}...
                        </div>
                      )}
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              {currentJobId && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded group-data-[collapsible=icon]:justify-center">
                        <Activity className="h-3 w-3 text-muted-foreground shrink-0" />
                        <span className="text-[12px] text-muted-foreground font-mono truncate group-data-[collapsible=icon]:hidden">
                          {currentJobId.substring(0, 8)}...
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="group-data-[collapsible=icon]:block hidden">
                      <div className="text-xs font-mono">{currentJobId}</div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
          ) : (
            <div className="mt-1 px-1.5 py-0.5 text-[12px] text-muted-foreground group-data-[collapsible=icon]:hidden">
              No active project
            </div>
          )}
        </SidebarHeader>

        <SidebarSeparator className="my-1" />

        {/* Navigation Items - High Density Icons */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-2 py-1 group-data-[collapsible=icon]:hidden">
            Navigation
          </SidebarGroupLabel>
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
                              className={cn(
                                "h-8 px-2 cursor-not-allowed opacity-60",
                                "group-data-[collapsible=icon]:w-8 group-data-[collapsible=icon]:px-0"
                              )}
                              aria-disabled
                            >
                              <item.icon className="h-4 w-4 shrink-0" />
                              <span className="text-[12px] group-data-[collapsible=icon]:hidden">{item.title}</span>
                            </SidebarMenuButton>
                          </TooltipTrigger>
                          <TooltipContent side="right" className="group-data-[collapsible=icon]:block hidden">
                            <div className="text-xs">{item.title}</div>
                            <div className="text-[10px] text-muted-foreground mt-0.5">
                              Select a project/job to open workbench
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ) : (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <SidebarMenuButton
                              asChild
                              isActive={isActive}
                              className={cn(
                                "h-8 px-2",
                                "group-data-[collapsible=icon]:w-8 group-data-[collapsible=icon]:px-0"
                              )}
                            >
                              <Link href={item.href}>
                                <item.icon className="h-4 w-4 shrink-0" />
                                <span className="text-[12px] group-data-[collapsible=icon]:hidden">{item.title}</span>
                              </Link>
                            </SidebarMenuButton>
                          </TooltipTrigger>
                          <TooltipContent side="right" className="group-data-[collapsible=icon]:block hidden">
                            <div className="text-xs">{item.title}</div>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
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
