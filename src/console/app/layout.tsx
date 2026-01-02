//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
import type React from "react"
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { Suspense } from "react"
import "./globals.css"
import { ThemeProvider } from "@/components/theme-provider"
import { DocumentProvider } from "@/contexts/document-context"
import { ClientInitializer } from "@/components/client-init"
import { Toaster } from "@/components/ui/toaster"
import { ErrorBoundary } from "@/components/ui/error-boundary"
import { NavMain } from "@/components/nav-main"
import { NavProject } from "@/components/nav-project"
import { TopBar } from "@/components/topbar"
import { MainContentArea } from "@/components/main-content-area"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
})

export const metadata: Metadata = {
  title: "Project Vyasa Console",
  description: "Project Vyasa research factory console for knowledge graph management",
    generator: 'v0.dev'
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} light`}>
      <body className={`${inter.className} blueprint-grid`}>
        <ThemeProvider defaultTheme="light" forcedTheme="light">
          <ErrorBoundary>
            <DocumentProvider>
              <ClientInitializer />
              {/* Dual-Sidebar Navigation System */}
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
              <Toaster />
            </DocumentProvider>
          </ErrorBoundary>
        </ThemeProvider>
      </body>
    </html>
  )
}
