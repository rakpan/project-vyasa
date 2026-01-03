//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { usePathname } from "next/navigation"
import { Suspense } from "react"
import { NavMain } from "@/components/nav-main"
import { NavProject } from "@/components/nav-project"
import { TopBar } from "@/components/topbar"
import { MainContentArea } from "@/components/main-content-area"

interface ConditionalLayoutProps {
  children: React.ReactNode
  excludePaths?: string[]
}

/**
 * ConditionalLayout - Renders full layout structure only for authenticated pages
 * Excludes navigation for login and other excluded paths
 */
export function ConditionalLayout({ children, excludePaths = ["/login"] }: ConditionalLayoutProps) {
  const pathname = usePathname()
  const isExcluded = excludePaths.some((path) => pathname.startsWith(path))

  // For excluded paths (like /login), render children without layout structure
  if (isExcluded) {
    return <>{children}</>
  }

  // For authenticated pages, render full layout with sidebars
  return (
    <div className="flex h-screen">
      {/* Global Navigation Rail */}
      <NavMain />
      
      {/* Project Sub-Navigation (conditional) */}
      <Suspense fallback={null}>
        <NavProject />
      </Suspense>

      {/* Main Content Area - Dynamic margin based on nav visibility */}
      <MainContentArea>
        <TopBar />
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </MainContentArea>
    </div>
  )
}

