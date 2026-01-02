//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { AlertCircle, CheckCircle2, XCircle } from "lucide-react"
import { toast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"

type ReframingProposal = {
  proposal_id?: string
  conflict_summary?: string
  proposed_pivot?: string
  architectural_rationale?: string
  assumptions_changed?: string[]
  what_stays_true?: string[]
  evidence_anchors?: string[]
  pivot_type?: string
  conflict_hash?: string
}

interface InterruptPanelProps {
  jobId: string
  projectId: string
  open: boolean
  onClose: () => void
}

/**
 * Interrupt Panel - Displays reframing proposal when workflow is paused
 * Shows conflict summary, proposed pivot, and impact analysis
 * Provides Approve & Resume and Modify Scope actions
 */
export function InterruptPanel({ jobId, projectId, open, onClose }: InterruptPanelProps) {
  const router = useRouter()
  const [proposal, setProposal] = useState<ReframingProposal | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>("")
  const [editedPivot, setEditedPivot] = useState("")
  const [submitting, setSubmitting] = useState(false)

  // Fetch reframing proposal when panel opens
  useEffect(() => {
    if (!open || !jobId) return

    const loadProposal = async () => {
      setLoading(true)
      setError("")
      try {
        const resp = await fetch(`/api/proxy/orchestrator/api/jobs/${jobId}/signoff`)
        if (!resp.ok) {
          throw new Error(`Failed to load proposal (${resp.status})`)
        }
        const data = await resp.json()
        if (data.proposal) {
          setProposal(data.proposal)
          setEditedPivot(data.proposal.proposed_pivot || "")
        } else {
          setError("No reframing proposal found for this job.")
        }
      } catch (e: any) {
        setError(e?.message || "Failed to load reframing proposal.")
        console.error("Failed to load proposal:", e)
      } finally {
        setLoading(false)
      }
    }

    loadProposal()
  }, [open, jobId])

  const handleApproveAndResume = async () => {
    if (!proposal) return
    setSubmitting(true)
    setError("")

    try {
      const resp = await fetch(`/api/proxy/orchestrator/api/jobs/${jobId}/signoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "accept",
          proposal_id: proposal.proposal_id,
          edited_pivot: editedPivot !== proposal.proposed_pivot ? editedPivot : undefined,
        }),
      })

      if (!resp.ok) {
        const msg = await resp.text()
        throw new Error(msg || "Failed to approve and resume workflow")
      }

      const data = await resp.json()
      toast({
        title: "Reframing approved",
        description: "Workflow resumed from checkpoint.",
      })

      // If a new job was created, navigate to it; otherwise refresh current job
      if (data.new_job_id) {
        router.push(`/research-workbench?projectId=${projectId}&jobId=${data.new_job_id}`)
      } else {
        // Resume from same job - refresh page to see updated status
        router.refresh()
      }
      onClose()
    } catch (e: any) {
      setError(e?.message || "Failed to approve and resume workflow.")
      console.error("Failed to approve reframe:", e)
    } finally {
      setSubmitting(false)
    }
  }

  const handleModifyScope = () => {
    // Navigate to project settings or scope editor
    router.push(`/projects/${projectId}?tab=scope`)
    onClose()
  }

  if (!open) return null

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-amber-500" />
            <span>Workflow Paused - Reframing Required</span>
            {proposal?.proposal_id && (
              <Badge variant="outline" className="text-xs">
                #{proposal.proposal_id.slice(0, 8)}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            A structural conflict was detected that requires human judgment. Review the proposal below and decide how to proceed.
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="py-8 text-center text-sm text-muted-foreground">Loading reframing proposal...</div>
        )}

        {error && (
          <div className="p-3 bg-destructive/10 border border-destructive/50 rounded-md text-sm text-destructive">
            {error}
          </div>
        )}

        {!loading && proposal && (
          <div className="space-y-4">
            {/* Conflict Summary */}
            <div className="space-y-2">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <XCircle className="h-4 w-4 text-amber-500" />
                Conflict Summary
              </h3>
              <p className="text-sm text-muted-foreground bg-amber-50 p-3 rounded-md border border-amber-200">
                {proposal.conflict_summary || "Structural conflict detected in extracted knowledge."}
              </p>
              {proposal.conflict_hash && (
                <p className="text-xs text-muted-foreground">
                  Conflict Hash: <code className="bg-muted px-1 rounded">{proposal.conflict_hash.slice(0, 16)}</code>
                </p>
              )}
            </div>

            {/* Proposed Pivot (Editable) */}
            <div className="space-y-2">
              <label className="text-sm font-semibold flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                Proposed Reframing
              </label>
              <Textarea
                value={editedPivot}
                onChange={(e) => setEditedPivot(e.target.value)}
                className="min-h-[120px] text-sm"
                placeholder="Enter your reframed thesis or research question..."
                disabled={submitting}
              />
              <p className="text-xs text-muted-foreground">
                You can modify the proposed pivot before approving. Changes will be applied when resuming the workflow.
              </p>
            </div>

            {/* Architectural Rationale */}
            {proposal.architectural_rationale && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Rationale</h3>
                <p className="text-sm text-muted-foreground bg-slate-50 p-3 rounded-md border border-slate-200">
                  {proposal.architectural_rationale}
                </p>
              </div>
            )}

            {/* Impact Summary */}
            <div className="grid grid-cols-2 gap-4">
              {/* Assumptions Changed */}
              {proposal.assumptions_changed && proposal.assumptions_changed.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-amber-600">Assumptions to Change</h3>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    {proposal.assumptions_changed.map((assumption, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-amber-500 mt-1">•</span>
                        <span>{assumption}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* What Stays True */}
              {proposal.what_stays_true && proposal.what_stays_true.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-emerald-600">What Stays True</h3>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    {proposal.what_stays_true.map((truth, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-emerald-500 mt-1">•</span>
                        <span>{truth}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Evidence Anchors */}
            {proposal.evidence_anchors && proposal.evidence_anchors.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Evidence Anchors</h3>
                <div className="flex flex-wrap gap-2">
                  {proposal.evidence_anchors.map((anchor, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs">
                      {anchor}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-200">
              <div className="text-xs text-muted-foreground">
                {submitting ? "Processing..." : "Workflow will resume from checkpoint after approval."}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleModifyScope} disabled={submitting}>
                  Modify Scope
                </Button>
                <Button onClick={handleApproveAndResume} disabled={submitting || !editedPivot.trim()}>
                  Approve & Resume
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

