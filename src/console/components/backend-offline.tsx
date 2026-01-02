//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useState } from "react"
import { AlertCircle, RefreshCw, CheckCircle2, XCircle, Wifi, WifiOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface ConnectivityCheck {
  service: string
  url: string
  status: "checking" | "online" | "offline"
  error?: string
}

/**
 * Backend Offline Component - Provides actionable connectivity checks
 * Instead of generic error, shows step-by-step diagnostics
 */
export function BackendOffline() {
  const [checks, setChecks] = useState<ConnectivityCheck[]>([
    { service: "Orchestrator", url: "/api/proxy/orchestrator/health", status: "checking" },
    { service: "Graph (ArangoDB)", url: "/api/proxy/orchestrator/health", status: "checking" },
    { service: "Vector (Qdrant)", url: "/api/proxy/orchestrator/health", status: "checking" },
  ])
  const [isChecking, setIsChecking] = useState(false)

  const performChecks = async () => {
    setIsChecking(true)
    const newChecks: ConnectivityCheck[] = []

    for (const check of checks) {
      try {
        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(), 5000)

        const resp = await fetch(check.url, {
          method: "GET",
          signal: controller.signal,
          cache: "no-store",
        })

        clearTimeout(timeout)

        newChecks.push({
          ...check,
          status: resp.ok ? "online" : "offline",
          error: resp.ok ? undefined : `HTTP ${resp.status}`,
        })
      } catch (err: any) {
        newChecks.push({
          ...check,
          status: "offline",
          error: err?.message || "Connection failed",
        })
      }
    }

    setChecks(newChecks)
    setIsChecking(false)
  }

  // Auto-check on mount
  useEffect(() => {
    performChecks()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const allOnline = checks.every((c) => c.status === "online")
  const allOffline = checks.every((c) => c.status === "offline")
  const someOffline = checks.some((c) => c.status === "offline")

  return (
    <div className="h-full flex items-center justify-center p-8">
      <Card className="max-w-lg w-full border-amber-200 bg-amber-50/50">
        <CardHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-12 w-12 rounded-lg bg-amber-100 flex items-center justify-center">
              <WifiOff className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                Backend Connectivity Issue
                {allOffline && <Badge variant="destructive" className="text-xs">All Services Offline</Badge>}
                {someOffline && !allOffline && <Badge variant="secondary" className="text-xs">Partial Outage</Badge>}
              </CardTitle>
              <CardDescription className="text-sm">
                {allOffline
                  ? "Unable to connect to backend services. Check the steps below."
                  : "Some services are unreachable. Review connectivity status."}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Connectivity Status */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Service Status</h4>
            <div className="space-y-1.5">
              {checks.map((check, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 bg-white rounded-md border border-slate-200"
                >
                  <div className="flex items-center gap-2">
                    {check.status === "checking" && (
                      <RefreshCw className="h-4 w-4 text-muted-foreground animate-spin" />
                    )}
                    {check.status === "online" && <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
                    {check.status === "offline" && <XCircle className="h-4 w-4 text-rose-600" />}
                    <span className="text-sm font-medium">{check.service}</span>
                  </div>
                  <Badge
                    variant={check.status === "online" ? "default" : "destructive"}
                    className="text-[10px]"
                  >
                    {check.status === "checking" ? "Checking..." : check.status === "online" ? "Online" : "Offline"}
                  </Badge>
                </div>
              ))}
            </div>
          </div>

          {/* Actionable Steps */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Troubleshooting Steps</h4>
            <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
              <li>
                <strong>Check Docker services:</strong> Run <code className="bg-slate-100 px-1 rounded">docker ps</code> to verify containers are running
              </li>
              <li>
                <strong>Verify network:</strong> Ensure <code className="bg-slate-100 px-1 rounded">vyasa-net</code> Docker network exists
              </li>
              <li>
                <strong>Check logs:</strong> Review orchestrator logs with{" "}
                <code className="bg-slate-100 px-1 rounded">docker logs vyasa-orchestrator</code>
              </li>
              <li>
                <strong>Restart stack:</strong> Use <code className="bg-slate-100 px-1 rounded">./scripts/run_stack.sh restart</code> if needed
              </li>
              <li>
                <strong>Port conflicts:</strong> Verify ports 8000, 8529, 6333 are not in use by other processes
              </li>
            </ol>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2 pt-2 border-t border-slate-200">
            <Button onClick={performChecks} disabled={isChecking} variant="outline" size="sm" className="flex-1">
              <RefreshCw className={cn("h-4 w-4 mr-2", isChecking && "animate-spin")} />
              {isChecking ? "Checking..." : "Re-check Connectivity"}
            </Button>
            <Button
              onClick={() => window.location.reload()}
              variant="default"
              size="sm"
              className="flex-1"
            >
              <Wifi className="h-4 w-4 mr-2" />
              Reload Page
            </Button>
          </div>

          {allOnline && (
            <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-md">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <p className="text-xs text-emerald-900">
                <strong>All services online.</strong> The issue may have resolved. Try refreshing the page.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

