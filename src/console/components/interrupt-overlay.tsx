import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

type Proposal = {
  proposal_id?: string
  conflict_summary?: string
  proposed_pivot?: string
  assumptions_changed?: string[]
  what_stays_true?: string[]
  evidence_anchors?: string[]
}

interface InterruptOverlayProps {
  open: boolean
  proposal?: Proposal
  onApprove: () => void
  onModify: () => void
}

export function InterruptOverlay({ open, proposal, onApprove, onModify }: InterruptOverlayProps) {
  if (!open) return null

  return (
    <Dialog open={open}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Badge variant="outline">Awaiting Reframe</Badge>
            {proposal?.proposal_id && <span className="text-xs text-muted-foreground">#{proposal.proposal_id}</span>}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div>
            <p className="font-medium">Summary</p>
            <p className="text-muted-foreground">{proposal?.conflict_summary || "Reframing requested."}</p>
          </div>
          <div>
            <p className="font-medium">Proposed Pivot</p>
            <p className="text-muted-foreground">{proposal?.proposed_pivot || "Refine scope to resolve conflict."}</p>
          </div>
          {proposal?.assumptions_changed && proposal.assumptions_changed.length > 0 && (
            <div>
              <p className="font-medium">Assumptions to change</p>
              <ul className="list-disc list-inside text-muted-foreground">
                {proposal.assumptions_changed.map((a) => <li key={a}>{a}</li>)}
              </ul>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onModify}>Modify Scope</Button>
          <Button onClick={onApprove}>Approve & Resume</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
