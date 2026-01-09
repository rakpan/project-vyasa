"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, XCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { toast } from "@/hooks/use-toast"

interface HealthStatus {
  orchestrator: boolean
  reranker?: boolean
  vision?: boolean
  active_prompts: Record<string, number>
}

export function HealthTab() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadHealth()
  }, [])

  const loadHealth = async () => {
    try {
      setIsLoading(true)
      
      // Load orchestrator health
      const healthResponse = await fetch("/api/proxy/orchestrator/health?deep=true")
      const orchestratorHealthy = healthResponse.ok

      // Load active prompt versions
      const promptsResponse = await fetch("/api/proxy/orchestrator/api/settings/prompts")
      const prompts: any[] = promptsResponse.ok ? await promptsResponse.json() : []
      
      // Extract active versions
      const activePrompts: Record<string, number> = {}
      prompts.forEach((p) => {
        if (!activePrompts[p.prompt_id] || p.version > activePrompts[p.prompt_id]) {
          activePrompts[p.prompt_id] = p.version
        }
      })

      // Try to check reranker (optional - check health endpoint if available)
      let rerankerHealthy: boolean | undefined
      try {
        // Reranker health check would go here if endpoint exists
        // For now, we'll skip it as it's optional
        rerankerHealthy = undefined
      } catch {
        // Reranker check is optional
      }

      setHealth({
        orchestrator: orchestratorHealthy,
        reranker: rerankerHealthy,
        active_prompts: activePrompts,
      })
    } catch (error) {
      console.error("Failed to load health:", error)
      toast({
        title: "Error",
        description: "Failed to load health status.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return <div className="text-center py-8 text-muted-foreground">Loading health status...</div>
  }

  if (!health) {
    return <div className="text-center py-8 text-muted-foreground">Unable to load health status</div>
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Service Health</CardTitle>
              <CardDescription>Status of core services and dependencies</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={loadHealth}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {health.orchestrator ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500" />
              )}
              <span className="font-medium">Orchestrator</span>
            </div>
            <Badge variant={health.orchestrator ? "default" : "destructive"}>
              {health.orchestrator ? "Healthy" : "Unavailable"}
            </Badge>
          </div>

          {health.reranker !== undefined && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {health.reranker ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500" />
                )}
                <span className="font-medium">Reranker</span>
              </div>
              <Badge variant={health.reranker ? "default" : "destructive"}>
                {health.reranker ? "Healthy" : "Unavailable"}
              </Badge>
            </div>
          )}

          {health.vision !== undefined && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {health.vision ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500" />
                )}
                <span className="font-medium">Vision</span>
              </div>
              <Badge variant={health.vision ? "default" : "destructive"}>
                {health.vision ? "Healthy" : "Unavailable"}
              </Badge>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Prompt Versions</CardTitle>
          <CardDescription>Currently active prompt profile versions</CardDescription>
        </CardHeader>
        <CardContent>
          {Object.keys(health.active_prompts).length === 0 ? (
            <div className="text-sm text-muted-foreground">No active prompts found</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(health.active_prompts).map(([promptId, version]) => (
                <div key={promptId} className="flex items-center justify-between py-2 border-b last:border-0">
                  <code className="text-sm">{promptId}</code>
                  <Badge>v{version}</Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
