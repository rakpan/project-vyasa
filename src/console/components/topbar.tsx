//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import Link from "next/link"
import { Search as SearchIcon } from "lucide-react"
import { NvidiaIcon } from "@/components/nvidia-icon"
import { ThemeToggle } from "@/components/theme-toggle"
import { InfoModal } from "@/components/info-modal"
import { SettingsModal } from "@/components/settings-modal"
import { LogoutButton } from "@/components/logout-button"
import { SidebarTrigger } from "@/components/ui/sidebar"

export function TopBar() {
  return (
    <header className="border-b border-border/50 backdrop-blur-md dark:bg-background/95 bg-background sticky top-0 z-50 shadow-sm">
      <div className="container mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SidebarTrigger className="mr-2" />
          <NvidiaIcon className="h-8 w-8" />
          <div>
            <span className="text-xl font-bold gradient-text">Project Vyasa</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Link
            href="/rag"
            className="flex items-center gap-2 text-sm font-medium rounded-lg px-3 py-2 transition-colors border border-brand-nvidia/40 text-brand-nvidia bg-brand-nvidia/10 hover:bg-brand-nvidia/20 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-nvidia/50 dark:bg-brand-nvidia/20 dark:hover:bg-brand-nvidia/30 dark:border-brand-nvidia/50"
          >
            <SearchIcon className="h-4 w-4 text-current" />
            <span>RAG Search</span>
          </Link>
          <InfoModal />
          <SettingsModal />
          <LogoutButton />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

