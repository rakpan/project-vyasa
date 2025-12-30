"use client"

import { useState } from "react"
import { FileText, Network, FileEdit, Settings, ChevronLeft, ChevronRight } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface ZenNavigationProps {
  onNavigate?: (route: string) => void
}

/**
 * Icon-only collapsible sidebar navigation.
 * Zen-First: Minimal footprint, labels on hover.
 */
export function ZenNavigation({ onNavigate }: ZenNavigationProps) {
  const [collapsed, setCollapsed] = useState(false)

  const navItems = [
    { icon: FileText, label: "Projects", route: "/projects" },
    { icon: Network, label: "Graph", route: "/research-workbench" },
    { icon: FileEdit, label: "Manuscript", route: "/manuscript" },
    { icon: Settings, label: "Settings", route: "/settings" },
  ]

  return (
    <div
      className={cn(
        "h-full bg-muted/30 border-r border-border/50 transition-all duration-200",
        collapsed ? "w-12" : "w-16"
      )}
    >
      <div className="flex flex-col h-full py-2">
        {/* Collapse toggle */}
        <div className="px-2 pb-2 border-b border-border/30">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full justify-center"
                  onClick={() => setCollapsed(!collapsed)}
                >
                  {collapsed ? (
                    <ChevronRight className="h-4 w-4" />
                  ) : (
                    <ChevronLeft className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">{collapsed ? "Expand" : "Collapse"}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Navigation items */}
        <div className="flex-1 flex flex-col gap-1 px-2 pt-2">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <TooltipProvider key={item.route}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-center"
                      onClick={() => onNavigate?.(item.route)}
                    >
                      <Icon className="h-5 w-5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">{item.label}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )
          })}
        </div>
      </div>
    </div>
  )
}

