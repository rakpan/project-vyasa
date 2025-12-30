"use client"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { useState } from "react"

type MergeAliasDialogProps = {
  open: boolean
  onClose: () => void
  sourceId: string | null
  targetId: string | null
  onConfirm: (sourceId: string, targetId: string) => Promise<void>
}

export function MergeAliasDialog({ open, onClose, sourceId, targetId, onConfirm }: MergeAliasDialogProps) {
  const [loading, setLoading] = useState(false)
  const canMerge = !!sourceId && !!targetId

  const handleConfirm = async () => {
    if (!canMerge || !sourceId || !targetId) return
    setLoading(true)
    try {
      await onConfirm(sourceId, targetId)
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Merge / Alias Entities</DialogTitle>
          <DialogDescription>
            This creates an alias relationship and moves evidence/claims from the source to the target. No data is deleted.
          </DialogDescription>
        </DialogHeader>
        <div className="text-sm space-y-1">
          <div><span className="font-semibold">Source:</span> {sourceId || "Select source"}</div>
          <div><span className="font-semibold">Target:</span> {targetId || "Select target"}</div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={!canMerge || loading}>
            {loading ? "Merging..." : "Confirm Merge"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
