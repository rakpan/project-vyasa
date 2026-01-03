"use client"

/**
 * RigorToggleModal Component
 * Modal for changing project rigor level with explanation and warning
 */

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertTriangle, Loader2 } from "lucide-react"
import { toast } from "@/hooks/use-toast"

type RigorLevel = "exploratory" | "conservative"

interface RigorToggleModalProps {
  open: boolean
  onClose: () => void
  currentRigor: RigorLevel
  projectId: string
  onRigorChanged?: (newRigor: RigorLevel) => void
}

export function RigorToggleModal({
  open,
  onClose,
  currentRigor,
  projectId,
  onRigorChanged,
}: RigorToggleModalProps) {
  const [selectedRigor, setSelectedRigor] = useState<RigorLevel>(currentRigor)
  const [isLoading, setIsLoading] = useState(false)

  const handleSave = async () => {
    if (selectedRigor === currentRigor) {
      onClose()
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/rigor`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rigor_level: selectedRigor }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || "Failed to update rigor level")
      }

      toast({
        title: "Rigor level updated",
        description: `Project rigor changed to ${selectedRigor}. This will affect future jobs only.`,
      })

      onRigorChanged?.(selectedRigor)
      onClose()
    } catch (err: any) {
      toast({
        title: "Error",
        description: err?.message || "Failed to update rigor level",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Change Rigor Level</DialogTitle>
          <DialogDescription>
            Adjust the rigor level for this project. This affects tone enforcement and precision policies.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Current Rigor Level</Label>
            <div className="text-sm text-muted-foreground capitalize">{currentRigor}</div>
          </div>

          <div className="space-y-2">
            <Label>Select New Rigor Level</Label>
            <RadioGroup value={selectedRigor} onValueChange={(v) => setSelectedRigor(v as RigorLevel)}>
              <div className="flex items-start space-x-2 p-3 rounded-md border border-border hover:bg-muted/50">
                <RadioGroupItem value="exploratory" id="exploratory" className="mt-1" />
                <Label htmlFor="exploratory" className="font-normal cursor-pointer flex-1">
                  <div>
                    <div className="font-medium">Exploratory</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Light-touch policies. Tone is flag-only. Precision uses policy defaults. Allows broader
                      interpretations and hypothesis generation.
                    </div>
                  </div>
                </Label>
              </div>
              <div className="flex items-start space-x-2 p-3 rounded-md border border-border hover:bg-muted/50">
                <RadioGroupItem value="conservative" id="conservative" className="mt-1" />
                <Label htmlFor="conservative" className="font-normal cursor-pointer flex-1">
                  <div>
                    <div className="font-medium">Conservative</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Stricter validation. Can enable tone rewrites when tone_enforcement is set to rewrite.
                      Higher precision requirements (typically 2 decimal places). More rigorous evidence standards.
                    </div>
                  </div>
                </Label>
              </div>
            </RadioGroup>
          </div>

          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="text-xs">
              <strong>Important:</strong> This change will only affect <strong>future jobs</strong> created after
              this update. Currently running or queued jobs will continue with their original rigor level.
            </AlertDescription>
          </Alert>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading || selectedRigor === currentRigor}>
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              "Save Changes"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

