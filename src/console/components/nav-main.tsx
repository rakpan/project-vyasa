//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { FolderKanban, BookText, Activity, Settings } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { ProjectLogo } from "@/components/project-logo"
import { cn } from "@/lib/utils"
import { NavFooter } from "./nav-footer"
import { StatusStrip } from "./status-strip"
import { ObservatoryTooltipContent } from "./observatory-tooltip"

interface NavItem {
  title: string
  href: string
  icon: React.ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  {
    title: "Projects",
    href: "/projects",
    icon: FolderKanban,
  },
  {
    title: "Knowledge Base",
    href: "/knowledge",
    icon: BookText,
  },
  {
    title: "Observatory",
    href: "/observatory",
    icon: Activity,
  },
  {
    title: "Settings",
    href: "/settings",
    icon: Settings,
  },
]

/**
 * Global Navigation Rail - Slim fixed sidebar for core actions
 * Visual: w-[72px] bg-muted border-r border-border
 */
export function NavMain() {
  const pathname = usePathname()

  return (
    <aside className="fixed left-0 top-0 h-screen w-[72px] bg-muted border-r border-border flex flex-col z-40">
      {/* Logo */}
      <div className="p-2 border-b border-border overflow-hidden">
        <Link href="/projects" className="block">
          <ProjectLogo align="left" />
        </Link>
      </div>

      {/* Core Actions */}
      <nav className="flex-1 flex flex-col items-center py-2 gap-1">
        <TooltipProvider delayDuration={200}>
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href || pathname?.startsWith(item.href + "/")
            const isObservatory = item.href === "/observatory"

            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <Link
                    href={item.href}
                    className={cn(
                      "h-9 w-9 rounded-md flex items-center justify-center transition-all duration-200",
                      "text-foreground hover:bg-background",
                      isActive && "bg-background shadow-[inset_2px_0_0_rgb(var(--primary))]"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </Link>
                </TooltipTrigger>
                {isObservatory ? (
                  <TooltipContent side="right" className="p-0 border-0 bg-transparent shadow-none">
                    <ObservatoryTooltipContent />
                  </TooltipContent>
                ) : (
                  <TooltipContent side="right" className="text-xs">
                    {item.title}
                  </TooltipContent>
                )}
              </Tooltip>
            )
          })}
        </TooltipProvider>
      </nav>

      {/* Status Strip - Thread ID and Checkpoint Info */}
      <StatusStrip />

      {/* Agent Heartbeat Footer */}
      <NavFooter />
    </aside>
  )
}
