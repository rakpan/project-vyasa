"use client"

import { useEffect, useMemo, useState } from "react"
import dynamic from "next/dynamic"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "@/hooks/use-toast"

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false })

interface MathOverlayProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  latex: string
  sympy: string
  projectId?: string
}

export function MathOverlay({ open, onOpenChange, latex, sympy, projectId }: MathOverlayProps) {
  const [code, setCode] = useState(sympy)
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setCode(sympy)
    setResult(null)
  }, [sympy])

  const handleVerify = async () => {
    setLoading(true)
    try {
      const resp = await fetch("/api/proxy/orchestrator/tools/math-sandbox", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latex, sympy: code, project_id: projectId }),
      })
      if (!resp.ok) {
        throw new Error(`Verify failed (${resp.status})`)
      }
      const data = await resp.json()
      setResult(data)
      toast({ title: "Verification complete", description: "MathSandbox returned results." })
    } catch (err: any) {
      toast({ title: "Verification failed", description: err?.message || "Unknown error", variant: "destructive" })
    } finally {
      setLoading(false)
    }
  }

  const handleFlag = async () => {
    try {
      await fetch("/api/proxy/orchestrator/logician/recalculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latex, sympy: code, project_id: projectId, reason: "user_correction" }),
      })
      toast({ title: "Flagged for recalculation", description: "Sent to Logician for Platinum Layer update." })
      onOpenChange(false)
    } catch (err: any) {
      toast({ title: "Flag failed", description: err?.message || "Unknown error", variant: "destructive" })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Math Sandbox</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card>
            <CardContent className="pt-4 space-y-2">
              <Label>LaTeX</Label>
              <Input value={latex} readOnly />
              <Label>SymPy</Label>
              <div className="h-64 border rounded-md overflow-hidden">
                <MonacoEditor
                  height="100%"
                  defaultLanguage="python"
                  value={code}
                  onChange={(v) => setCode(v || "")}
                  theme="vs-dark"
                  options={{ minimap: { enabled: false } }}
                />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 space-y-3">
              <div className="flex gap-2">
                <Button size="sm" onClick={handleVerify} disabled={loading}>
                  {loading ? "Verifying..." : "Verify"}
                </Button>
                <Button size="sm" variant="outline" onClick={handleFlag}>
                  Flag for Recalculation
                </Button>
              </div>
              <div className="text-sm text-muted-foreground">
                {result ? <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre> : "No results yet."}
              </div>
            </CardContent>
          </Card>
        </div>
      </DialogContent>
    </Dialog>
  )
}
