//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useProjectStore } from "@/state/useProjectStore"

/**
 * Main Content Area - Adjusts margin based on navigation visibility
 * Margin-left: 72px (nav-main) + 200px (nav-project if active) or just 72px
 */
export function MainContentArea({ children }: { children: React.ReactNode }) {
  const { activeProjectId } = useProjectStore()
  const marginLeft = activeProjectId ? "272px" : "72px" // 72px (nav-main) + 200px (nav-project)

  return (
    <div className="flex-1 flex flex-col transition-all duration-200" style={{ marginLeft }}>
      {children}
    </div>
  )
}

