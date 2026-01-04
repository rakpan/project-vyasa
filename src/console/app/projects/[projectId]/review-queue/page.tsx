"use client"

/**
 * Review Queue Page - Displays PENDING ReviewTasks for human approval.
 * 
 * Shows a list of review tasks with:
 * - Dispute summary
 * - Top sources (URL/domain)
 * - Extracted claim count
 * - Status badge
 * 
 * This is a minimal stub - no approve/reject actions yet.
 */

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, FileText, ExternalLink, Clock, AlertCircle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { listReviewTasks } from "@/services/reviewQueueService"
import type { ReviewTask } from "@/types/review"

export default function ReviewQueuePage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.projectId as string
  
  const [tasks, setTasks] = useState<ReviewTask[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Fetch PENDING review tasks
  useEffect(() => {
    if (!projectId) return
    
    const fetchTasks = async () => {
      setIsLoading(true)
      setError(null)
      
      try {
        const reviewTasks = await listReviewTasks(projectId, "PENDING", 50)
        setTasks(reviewTasks)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to load review tasks"
        setError(errorMessage)
        console.error("Failed to fetch review tasks:", err)
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchTasks()
  }, [projectId])
  
  // Extract top sources from candidate claims
  const getTopSources = (task: ReviewTask): Array<{ url?: string; domain?: string }> => {
    // Extract unique sources from claims (if they have provenance metadata)
    // For now, return empty array as web augmentation sources aren't in claim structure yet
    // This is a placeholder for future enhancement
    return []
  }
  
  // Get dispute summary (placeholder - would come from DisputeContext)
  const getDisputeSummary = (task: ReviewTask): string => {
    // For now, use a generic message
    // In the future, this would fetch DisputeContext by dispute_id
    return `Dispute ${task.dispute_id.slice(0, 8)}... requires review`
  }
  
  return (
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push(`/projects/${projectId}`)}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Review Queue</h1>
          <p className="text-muted-foreground">
            Pending review tasks requiring human approval
          </p>
        </div>
      </div>
      
      {/* Error State */}
      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      
      {/* Loading State */}
      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-64" />
                <Skeleton className="h-4 w-48 mt-2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      
      {/* Empty State */}
      {!isLoading && !error && tasks.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Pending Reviews</h3>
            <p className="text-muted-foreground">
              There are no pending review tasks for this project.
            </p>
          </CardContent>
        </Card>
      )}
      
      {/* Task List */}
      {!isLoading && !error && tasks.length > 0 && (
        <div className="space-y-4">
          {tasks.map((task) => (
            <Card key={task.review_id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="text-lg mb-2">
                      {getDisputeSummary(task)}
                    </CardTitle>
                    <CardDescription className="flex items-center gap-4">
                      <span className="flex items-center gap-1">
                        <FileText className="h-3 w-3" />
                        {task.candidate_claims.length} claim{task.candidate_claims.length !== 1 ? 's' : ''}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(task.created_at).toLocaleDateString()}
                      </span>
                    </CardDescription>
                  </div>
                  <Badge
                    variant={
                      task.status === "PENDING" ? "default" :
                      task.status === "APPROVED" ? "secondary" :
                      task.status === "REJECTED" ? "destructive" :
                      "outline"
                    }
                  >
                    {task.status}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {/* Source Quality Score */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Source Quality:</span>
                    <Badge variant="outline" className="text-xs">
                      {(task.source_quality_score * 100).toFixed(0)}%
                    </Badge>
                  </div>
                  
                  {/* Top Sources (placeholder) */}
                  {getTopSources(task).length > 0 && (
                    <div className="space-y-1">
                      <span className="text-sm font-medium">Sources:</span>
                      <div className="flex flex-wrap gap-2">
                        {getTopSources(task).map((source, idx) => (
                          <a
                            key={idx}
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-primary hover:underline flex items-center gap-1"
                          >
                            {source.domain || source.url}
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Claim Preview */}
                  {task.candidate_claims.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-sm font-medium">Sample Claims:</span>
                      <div className="space-y-1">
                        {task.candidate_claims.slice(0, 3).map((claim) => (
                          <div
                            key={claim.claim_id}
                            className="text-xs text-muted-foreground p-2 bg-muted/50 rounded"
                          >
                            {claim.claim_text || `${claim.subject} ${claim.predicate} ${claim.object}`}
                          </div>
                        ))}
                        {task.candidate_claims.length > 3 && (
                          <p className="text-xs text-muted-foreground">
                            +{task.candidate_claims.length - 3} more claim{task.candidate_claims.length - 3 !== 1 ? 's' : ''}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Action Placeholder */}
                  <div className="pt-2 border-t">
                    <p className="text-xs text-muted-foreground italic">
                      Approve/Reject actions coming soon
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

