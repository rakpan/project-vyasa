"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ExternalLink, CheckCircle2, XCircle, Loader2 } from "lucide-react"
import { toast } from "@/hooks/use-toast"

interface CandidateFact {
  fact_id: string
  subject: string
  predicate: string
  object: string
  confidence: number
  promotion_state: "candidate" | "canonical"
  created_at: string
}

interface ExternalReference {
  reference_id: string
  project_id: string
  content_raw: string
  source_name: string
  source_url?: string
  extracted_at: string
  tags: string[]
  status: string
}

interface ReferenceReviewPanelProps {
  referenceId: string
  onPromoted?: () => void
  onRejected?: () => void
}

export function ReferenceReviewPanel({
  referenceId,
  onPromoted,
  onRejected,
}: ReferenceReviewPanelProps) {
  const [reference, setReference] = useState<ExternalReference | null>(null)
  const [candidateFacts, setCandidateFacts] = useState<CandidateFact[]>([])
  const [selectedFactIds, setSelectedFactIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [promoting, setPromoting] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadReference()
  }, [referenceId])

  const loadReference = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/proxy/orchestrator/api/knowledge/references/${referenceId}`)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Failed to load reference: ${response.statusText}`)
      }

      const data = await response.json()
      setReference(data.reference)
      
      // Filter to only candidate facts (not already promoted)
      const candidates = (data.candidate_facts || []).filter(
        (fact: CandidateFact) => fact.promotion_state === "candidate"
      )
      setCandidateFacts(candidates)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load reference"
      setError(message)
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSelectFact = (factId: string, checked: boolean) => {
    const newSelected = new Set(selectedFactIds)
    if (checked) {
      newSelected.add(factId)
    } else {
      newSelected.delete(factId)
    }
    setSelectedFactIds(newSelected)
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedFactIds(new Set(candidateFacts.map(f => f.fact_id)))
    } else {
      setSelectedFactIds(new Set())
    }
  }

  const handlePromoteSelected = async () => {
    if (selectedFactIds.size === 0) {
      toast({
        title: "No facts selected",
        description: "Please select at least one fact to promote.",
        variant: "destructive",
      })
      return
    }

    setPromoting(true)
    try {
      const response = await fetch(`/api/proxy/orchestrator/api/knowledge/references/${referenceId}/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fact_ids: Array.from(selectedFactIds),
          mode: "manual",
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Promotion failed: ${response.statusText}`)
      }

      const result = await response.json()
      
      toast({
        title: "Promotion successful",
        description: `Promoted ${result.promoted_count} fact(s) to canonical knowledge.`,
      })

      setSelectedFactIds(new Set())
      onPromoted?.()
      loadReference() // Reload to update status
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to promote facts"
      toast({
        title: "Promotion failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setPromoting(false)
    }
  }

  const handleAutoPromote = async () => {
    setPromoting(true)
    try {
      const response = await fetch(`/api/proxy/orchestrator/api/knowledge/references/${referenceId}/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "auto",
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Auto-promotion failed: ${response.statusText}`)
      }

      const result = await response.json()
      
      toast({
        title: "Auto-promotion complete",
        description: `Promoted ${result.promoted_count} fact(s) meeting threshold criteria.`,
      })

      onPromoted?.()
      loadReference() // Reload to update status
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to auto-promote facts"
      toast({
        title: "Auto-promotion failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setPromoting(false)
    }
  }

  const handleReject = async () => {
    if (!confirm("Are you sure you want to reject this reference? Facts will not be deleted but the reference will be marked as rejected.")) {
      return
    }

    setRejecting(true)
    try {
      const response = await fetch(`/api/proxy/orchestrator/api/knowledge/references/${referenceId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Rejection failed: ${response.statusText}`)
      }

      toast({
        title: "Reference rejected",
        description: "The reference has been marked as rejected.",
      })

      onRejected?.()
      loadReference() // Reload to update status
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to reject reference"
      toast({
        title: "Rejection failed",
        description: message,
        variant: "destructive",
      })
    } finally {
      setRejecting(false)
    }
  }

  const formatConfidence = (confidence: number) => {
    return (confidence * 100).toFixed(1) + "%"
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      INGESTED: "default",
      EXTRACTING: "secondary",
      EXTRACTED: "default",
      NEEDS_REVIEW: "secondary",
      PROMOTED: "outline",
      REJECTED: "destructive",
    }
    return <Badge variant={variants[status] || "default"}>{status}</Badge>
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">Loading reference...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error || !reference) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center py-8">
            <p className="text-sm text-destructive">{error || "Reference not found"}</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={loadReference}
            >
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  const allSelected = candidateFacts.length > 0 && selectedFactIds.size === candidateFacts.length
  const someSelected = selectedFactIds.size > 0 && selectedFactIds.size < candidateFacts.length

  return (
    <div className="space-y-4">
      {/* Reference Metadata */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>Reference Details</CardTitle>
              <CardDescription className="mt-1">
                Source: {reference.source_name} • {new Date(reference.extracted_at).toLocaleString()}
              </CardDescription>
            </div>
            {getStatusBadge(reference.status)}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {reference.source_url && (
            <div className="flex items-center gap-2">
              <ExternalLink className="h-4 w-4 text-muted-foreground" />
              <a
                href={reference.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                {reference.source_url}
              </a>
            </div>
          )}
          
          {reference.tags && reference.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {reference.tags.map((tag) => (
                <Badge key={tag} variant="outline">{tag}</Badge>
              ))}
            </div>
          )}

          <div className="rounded-md bg-muted p-3 max-h-32 overflow-y-auto">
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {reference.content_raw}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Candidate Facts Table */}
      <Card>
        <CardHeader>
          <CardTitle>Candidate Facts</CardTitle>
          <CardDescription>
            {candidateFacts.length} candidate fact(s) available for promotion
          </CardDescription>
        </CardHeader>
        <CardContent>
          {candidateFacts.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              No candidate facts available. All facts may have been promoted already.
            </div>
          ) : (
            <div className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={allSelected}
                        onCheckedChange={handleSelectAll}
                        aria-label="Select all facts"
                      />
                    </TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Predicate</TableHead>
                    <TableHead>Object</TableHead>
                    <TableHead className="text-right">Confidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {candidateFacts.map((fact) => (
                    <TableRow key={fact.fact_id}>
                      <TableCell>
                        <Checkbox
                          checked={selectedFactIds.has(fact.fact_id)}
                          onCheckedChange={(checked) =>
                            handleSelectFact(fact.fact_id, checked as boolean)
                          }
                          aria-label={`Select fact ${fact.fact_id}`}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{fact.subject}</TableCell>
                      <TableCell>{fact.predicate}</TableCell>
                      <TableCell>{fact.object}</TableCell>
                      <TableCell className="text-right">
                        <Badge
                          variant={
                            fact.confidence >= 0.85 ? "default" : fact.confidence >= 0.7 ? "secondary" : "outline"
                          }
                        >
                          {formatConfidence(fact.confidence)}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-4 border-t">
                <Button
                  onClick={handlePromoteSelected}
                  disabled={promoting || rejecting || selectedFactIds.size === 0}
                  className="flex items-center gap-2"
                >
                  {promoting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  Promote Selected ({selectedFactIds.size})
                </Button>

                <Button
                  variant="outline"
                  onClick={handleAutoPromote}
                  disabled={promoting || rejecting}
                  className="flex items-center gap-2"
                >
                  {promoting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  Auto Promote (Threshold)
                </Button>

                <Button
                  variant="destructive"
                  onClick={handleReject}
                  disabled={promoting || rejecting}
                  className="flex items-center gap-2 ml-auto"
                >
                  {rejecting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                  Reject Reference
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

