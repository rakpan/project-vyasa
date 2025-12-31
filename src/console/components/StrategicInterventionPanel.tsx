import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "./ui/button"
import { Textarea } from "./ui/textarea"
import { cn } from "@/lib/utils"
import { toast } from "@/hooks/use-toast"

type SignoffResponse = {
  proposal?: {
    proposal_id: string
    conflict_summary: string
    conflict_hash: string
    pivot_type?: string
    proposed_pivot: string
    architectural_rationale?: string
    evidence_anchors?: string[]
    what_stays_true?: string[]
  }
  status?: string
}

type Props = {
  jobId: string
  projectId: string
}

export function StrategicInterventionPanel({ jobId, projectId }: Props) {
  const router = useRouter()
  const [proposal, setProposal] = useState<SignoffResponse["proposal"] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>("")
  const [editedPivot, setEditedPivot] = useState("")
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError("")
      try {
        const resp = await fetch(`/api/proxy/orchestrator/api/jobs/${jobId}/signoff`)
        if (!resp.ok) {
          throw new Error(`Signoff load failed (${resp.status})`)
        }
        const data: SignoffResponse = await resp.json()
        if (data.proposal) {
          setProposal(data.proposal)
          setEditedPivot(data.proposal.proposed_pivot || "")
        } else {
          setError("No proposal found for this job.")
        }
      } catch (e: any) {
        setError(e?.message || "Failed to load signoff data.")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [jobId])

  const handleAccept = async () => {
    if (!proposal) return
    setSubmitting(true)
    setError("")
    try {
      const resp = await fetch(`/api/proxy/orchestrator/api/jobs/${jobId}/signoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "accept", edited_pivot: editedPivot, proposal_id: proposal.proposal_id }),
      })
      if (!resp.ok) {
        const msg = await resp.text()
        throw new Error(msg || "Failed to accept reframe")
      }
      const data = await resp.json()
      const newJobId = data.new_job_id || data.newJobId
      toast({ title: "Reframe accepted. New analysis started." })
      if (newJobId) {
        const params = new URLSearchParams({ jobId: newJobId, projectId })
        router.push(`/research-workbench?${params.toString()}`)
      } else {
        router.push("/projects")
      }
    } catch (e: any) {
      setError(e?.message || "Failed to accept reframe.")
    } finally {
      setSubmitting(false)
    }
  }

  const handleReject = async () => {
    if (!proposal) return
    setSubmitting(true)
    setError("")
    try {
      const resp = await fetch(`/api/proxy/orchestrator/api/jobs/${jobId}/signoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reject", proposal_id: proposal.proposal_id }),
      })
      if (!resp.ok) {
        const msg = await resp.text()
        throw new Error(msg || "Failed to reject reframe")
      }
      toast({ title: "Reframe rejected. Job marked as failed." })
      router.push("/projects")
    } catch (e: any) {
      setError(e?.message || "Failed to reject reframe.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="w-full max-w-xl bg-card border border-border shadow-xl rounded-lg p-4 space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Strategic Intervention Required</h2>
        <p className="text-sm text-muted-foreground">A structural conflict was detected that requires human judgment.</p>
      </div>

      {error && <div className="text-sm text-destructive border border-destructive/50 rounded p-2">{error}</div>}
      {loading && <div className="text-sm text-muted-foreground">Loading proposal…</div>}

      {!loading && proposal && (
        <div className="space-y-3">
          <div className="space-y-1">
            <div className="text-sm font-medium">Conflict Summary</div>
            <div className="text-sm text-muted-foreground">{proposal.conflict_summary}</div>
            <div className="text-xs text-muted-foreground">
              Deadlock type: {proposal.pivot_type || "N/A"} · Hash: {(proposal.conflict_hash || "").slice(0, 8)}
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Reframed Thesis / Research Question</label>
            <Textarea
              value={editedPivot}
              onChange={(e) => setEditedPivot(e.target.value)}
              className="min-h-[100px]"
              disabled={submitting}
            />
          </div>

          <div className="space-y-1">
            <div className="text-sm font-medium">Rationale & Anchors</div>
            <div className="text-sm text-muted-foreground">{proposal.architectural_rationale || "No rationale provided."}</div>
            <ul className="list-disc list-inside text-sm text-muted-foreground">
              {(proposal.evidence_anchors || []).map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </div>

          <div className="space-y-1">
            <div className="text-sm font-medium">What Stays True</div>
            <ul className="list-disc list-inside text-sm text-muted-foreground">
              {(proposal.what_stays_true || []).map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>

          <div className="flex gap-3 pt-2">
            <Button disabled={submitting} onClick={handleAccept}>
              Accept &amp; Restart Analysis
            </Button>
            <Button variant="destructive" disabled={submitting} onClick={handleReject}>
              Reject Reframe
            </Button>
          </div>
          <div className={cn("text-xs text-muted-foreground", submitting && "italic")}>
            {submitting ? "Submitting decision…" : "Job is paused until you decide."}
          </div>
        </div>
      )}
    </div>
  )
}
