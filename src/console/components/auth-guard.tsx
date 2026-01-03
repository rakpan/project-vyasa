//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useEffect, useState } from "react"
import { useRouter, usePathname, useSearchParams } from "next/navigation"
import { useSession } from "next-auth/react"
import { useUserStore } from "@/state/useUserStore"

interface AuthGuardProps {
  children: React.ReactNode
  excludePaths?: string[]
}

/**
 * AuthGuard Component - Higher-Order Component for route protection
 * 
 * Checks for valid NextAuth session and redirects to /login if not authenticated.
 * Preserves URL parameters (threadId, jobId, projectId, pdfUrl) during redirect.
 * 
 * @param children - Child components to render if authenticated
 * @param excludePaths - Paths to exclude from authentication check (e.g., ["/login"])
 */
export function AuthGuard({ children, excludePaths = ["/login"] }: AuthGuardProps) {
  const { data: session, status } = useSession()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { setUser, setToken, clearAuth } = useUserStore()
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    // Skip auth check for excluded paths
    if (excludePaths.some((path) => pathname.startsWith(path))) {
      setIsChecking(false)
      return
    }

    // Wait for session to load
    if (status === "loading") {
      return
    }

    // If no session, redirect to login with preserved URL parameters
    if (status === "unauthenticated" || !session) {
      const loginUrl = new URL("/login", window.location.origin)
      
      // Preserve callback URL
      loginUrl.searchParams.set("callbackUrl", pathname)
      
      // Preserve all research context parameters
      const threadId = searchParams.get("threadId")
      const jobId = searchParams.get("jobId")
      const projectId = searchParams.get("projectId")
      const pdfUrl = searchParams.get("pdfUrl")
      
      if (threadId) loginUrl.searchParams.set("threadId", threadId)
      if (jobId) loginUrl.searchParams.set("jobId", jobId)
      if (projectId) loginUrl.searchParams.set("projectId", projectId)
      if (pdfUrl) loginUrl.searchParams.set("pdfUrl", pdfUrl)
      
      router.push(loginUrl.pathname + loginUrl.search)
      setIsChecking(false)
      return
    }

    // Session is valid - sync with user store
    if (session?.user) {
      setUser({
        id: session.user.id || session.user.email || "unknown",
        name: session.user.name || "User",
        email: session.user.email || "",
      })
      
      // Extract token from session if available
      // Note: NextAuth JWT is stored in httpOnly cookie, not accessible here
      // For API requests, we'll use NextAuth's built-in session handling
      setToken(null) // Token is managed server-side via cookies
    } else {
      clearAuth()
    }

    setIsChecking(false)
  }, [session, status, pathname, searchParams, router, excludePaths, setUser, setToken, clearAuth])

  // Show loading state while checking
  if (isChecking || status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background blueprint-grid">
        <div className="text-sm text-muted-foreground">Authenticating...</div>
      </div>
    )
  }

  // If path is excluded (e.g., /login), render children directly without layout
  if (excludePaths.some((path) => pathname.startsWith(path))) {
    return <>{children}</>
  }

  // If not authenticated, don't render (redirect is in progress)
  if (status === "unauthenticated" || !session) {
    return null
  }

  // Authenticated - render children (layout structure is provided by parent)
  return <>{children}</>
}

