"use client"

/**
 * Vision Enable Modal Component
 * Shows instructions for enabling Vision service via Docker Compose
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Eye, Copy, Check } from "lucide-react"
import { useState } from "react"

interface VisionEnableModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function VisionEnableModal({ open, onOpenChange }: VisionEnableModalProps) {
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null)

  const commands = [
    {
      label: "Turn Vision ON",
      command: "docker compose --profile vision up -d cortex-vision",
      description: "Starts the vision service container",
    },
    {
      label: "Turn Vision OFF (reclaim GPU memory)",
      command: "docker compose stop cortex-vision",
      description: "Stops the vision service and reclaims GPU memory",
    },
    {
      label: "Check Vision Status",
      command: "docker compose ps cortex-vision",
      description: "Shows whether the vision container is running",
    },
  ]

  const handleCopy = async (command: string) => {
    try {
      await navigator.clipboard.writeText(command)
      setCopiedCommand(command)
      setTimeout(() => setCopiedCommand(null), 2000)
    } catch (error) {
      console.error("Failed to copy command:", error)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-primary/15 flex items-center justify-center">
              <Eye className="h-5 w-5 text-primary" />
            </div>
            <DialogTitle className="text-xl font-bold">How to Enable Vision</DialogTitle>
          </div>
          <DialogDescription className="text-sm text-muted-foreground">
            Vision is an optional accelerator for processing scanned or image-heavy PDFs. Use these Docker Compose commands to enable or disable it.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs text-amber-800">
              <strong>Note:</strong> The UI toggle only reflects configuration and health status. It does not start or stop containers. You must run these commands on the server.
            </p>
          </div>

          {commands.map((cmd, idx) => (
            <div key={idx} className="space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-foreground">{cmd.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{cmd.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 px-3 py-2 bg-muted rounded-md text-xs font-mono text-foreground border border-border">
                  {cmd.command}
                </code>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopy(cmd.command)}
                  className="shrink-0"
                >
                  {copiedCommand === cmd.command ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          ))}

          <div className="bg-muted/50 border border-border rounded-lg p-3 mt-4">
            <p className="text-xs text-muted-foreground">
              <strong>Configuration:</strong> After starting the container, set <code className="bg-background px-1 py-0.5 rounded text-xs">VISION_ENABLED=true</code> in <code className="bg-background px-1 py-0.5 rounded text-xs">deploy/.env</code> to enable vision processing in the orchestrator.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
