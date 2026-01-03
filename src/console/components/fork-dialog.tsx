"use client"

/**
 * ForkDialog Component
 * Dialog for choosing rigor level when forking a manuscript block
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
import { Loader2 } from "lucide-react"

type RigorLevel = "exploratory" | "conservative"

interface ForkDialogProps {
  open: boolean
  onClose: () => void
  onFork: (rigorLevel: RigorLevel) => Promise<void>
  currentRigor?: string
}

export function ForkDialog({ open, onClose, onFork, currentRigor }: ForkDialogProps) {
  const [selectedRigor, setSelectedRigor] = useState<RigorLevel>("exploratory")
  const [isLoading, setIsLoading] = useState(false)

  const handleFork = async () => {
    setIsLoading(true)
    try {
      await onFork(selectedRigor)
      onClose()
    } catch (err) {
      console.error("Fork failed:", err)
      // Error handling can be added here (toast notification, etc.)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Fork Block</DialogTitle>
          <DialogDescription>
            Generate an alternate version of this block with a different rigor level.
            The original block will remain unchanged until you accept the fork.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Choose Rigor Level</Label>
            <RadioGroup value={selectedRigor} onValueChange={(v) => setSelectedRigor(v as RigorLevel)}>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="exploratory" id="exploratory" />
                <Label htmlFor="exploratory" className="font-normal cursor-pointer">
                  <div>
                    <div className="font-medium">Exploratory</div>
                    <div className="text-xs text-muted-foreground">
                      More flexible, allows broader interpretations
                    </div>
                  </div>
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="conservative" id="conservative" />
                <Label htmlFor="conservative" className="font-normal cursor-pointer">
                  <div>
                    <div className="font-medium">Conservative</div>
                    <div className="text-xs text-muted-foreground">
                      Stricter validation, higher precision requirements
                    </div>
                  </div>
                </Label>
              </div>
            </RadioGroup>
          </div>
          {currentRigor && (
            <div className="text-xs text-muted-foreground">
              Current rigor: <span className="font-medium capitalize">{currentRigor}</span>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleFork} disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Forking...
              </>
            ) : (
              "Fork Block"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

