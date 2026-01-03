//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { signIn } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ProjectLogo } from "@/components/project-logo"
import Image from "next/image"
import { Lock, Loader2 } from "lucide-react"

function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  // Preserve all URL parameters (callbackUrl, threadId, jobId, projectId, pdfUrl)
  const callbackUrl = searchParams.get("callbackUrl") || "/"
  const threadId = searchParams.get("threadId")
  const jobId = searchParams.get("jobId")
  const projectId = searchParams.get("projectId")
  const pdfUrl = searchParams.get("pdfUrl")
  
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    try {
      const result = await signIn("credentials", {
        password,
        redirect: false,
      })

      if (result?.error) {
        setError("Invalid password. Please try again.")
        setIsLoading(false)
      } else {
        // Reconstruct URL with all preserved parameters
        const targetUrl = new URL(callbackUrl, window.location.origin)
        if (threadId) targetUrl.searchParams.set("threadId", threadId)
        if (jobId) targetUrl.searchParams.set("jobId", jobId)
        if (projectId) targetUrl.searchParams.set("projectId", projectId)
        if (pdfUrl) targetUrl.searchParams.set("pdfUrl", pdfUrl)
        
        // Redirect to the callback URL with all parameters preserved
        router.push(targetUrl.pathname + targetUrl.search)
        router.refresh()
      }
    } catch (err) {
      setError("An error occurred. Please try again.")
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background blueprint-grid">
      <div className="w-full max-w-md p-8 space-y-8 bg-white border border-slate-200 rounded-lg shadow-md">
        {/* Branded Header with Logo */}
        <div className="text-center space-y-6">
          <div className="flex justify-center">
            <div className="relative h-12 w-64 overflow-hidden">
              <Image
                src="/vyasa_logo.jpeg"
                alt="Project Vyasa Logo"
                fill
                priority
                className="object-contain object-center"
              />
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-foreground tracking-tight">
              Project Vyasa
            </h1>
            <p className="text-sm text-muted-foreground">
              Secure access to the research factory console
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="password" className="text-sm font-medium text-foreground">
              Password
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter access password"
                className="pl-10 bg-background border-slate-200 text-foreground placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary"
                required
                disabled={isLoading}
                autoFocus
              />
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-md bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}

          <Button
            type="submit"
            className="w-full bg-foreground hover:bg-foreground/90 text-white font-medium"
            disabled={isLoading || !password}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Authenticating...
              </>
            ) : (
              <>
                <Lock className="mr-2 h-4 w-4" />
                Sign In
              </>
            )}
          </Button>
        </form>

        <div className="text-center text-xs text-muted-foreground pt-4 border-t border-slate-100">
          <p>Secure-by-Design • Project Vyasa Research Factory</p>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-background blueprint-grid">
        <div className="text-foreground">Loading...</div>
      </div>
    }>
      <LoginContent />
    </Suspense>
  )
}
