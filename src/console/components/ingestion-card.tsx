"use client"

/**
 * Ingestion Card Component
 * Per-file card showing pipeline state, progress, and actions
 */

import { useState } from "react"
import { FileText, X, RotateCw, AlertCircle, CheckCircle2, Clock, Loader2, Eye, AlertTriangle } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { VisionEnableModal } from "./vision-enable-modal"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { cn } from "@/lib/utils"

export type IngestionStatus =
  | "Queued"
  | "Extracting"
  | "Mapping"
  | "Verifying"
  | "Completed"
  | "Failed"

interface IngestionCardProps {
  filename: string
  status: IngestionStatus
  progress?: number // 0-100
  error?: string
  jobId?: string
  ingestionId?: string
  firstGlance?: {
    pages: number
    tables_detected: number
    figures_detected: number
    text_density: number
  }
  confidence?: "High" | "Medium" | "Low"
  warnings?: Array<{ code: string; severity: string; message: string }>
  triage?: { likely_scanned: boolean; preview_text_chars: number; pages_previewed: number }
  onRetry?: () => void
  onRemove?: () => void
  onViewDetails?: () => void
}

const STATUS_CONFIG: Record<
  IngestionStatus,
  { label: string; color: string; icon: React.ComponentType<{ className?: string }> }
> = {
  Queued: {
    label: "Queued",
    color: "bg-slate-500",
    icon: Clock,
  },
  Extracting: {
    label: "Extracting",
    color: "bg-blue-500",
    icon: Loader2,
  },
  Mapping: {
    label: "Mapping",
    color: "bg-purple-500",
    icon: Loader2,
  },
  Verifying: {
    label: "Verifying",
    color: "bg-amber-500",
    icon: Loader2,
  },
  Completed: {
    label: "Completed",
    color: "bg-emerald-500",
    icon: CheckCircle2,
  },
  Failed: {
    label: "Failed",
    color: "bg-red-500",
    icon: AlertCircle,
  },
}

export function IngestionCard({
  filename,
  status,
  progress = 0,
  error,
  jobId,
  ingestionId,
  firstGlance,
  confidence,
  warnings,
  triage,
  onRetry,
  onRemove,
  onViewDetails,
}: IngestionCardProps) {
  const [showErrorDialog, setShowErrorDialog] = useState(false)
  const [showVisionModal, setShowVisionModal] = useState(false)
  const config = STATUS_CONFIG[status]
  const Icon = config.icon
  const isActive = status === "Extracting" || status === "Mapping" || status === "Verifying"
  const isCompleted = status === "Completed"
  const isFailed = status === "Failed"
  
  // Check if this is a scanned PDF with vision off
  const visionWarning = warnings?.find((w) => w.code === "VISION_OFF_SCANNED_PDF")
  const isScannedWithVisionOff = visionWarning && triage?.likely_scanned

  // Calculate progress percentage
  const progressPercent = isCompleted ? 100 : progress

  return (
    <>
      <Card className={cn(
        "transition-all",
        isActive && "border-primary/50 shadow-sm",
        isFailed && "border-red-300 bg-red-50/30"
      )}>
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-4">
            {/* File Info */}
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className={cn(
                "p-2 rounded-md",
                isActive && "bg-primary/10",
                isCompleted && "bg-emerald-100",
                isFailed && "bg-red-100"
              )}>
                <FileText className={cn(
                  "h-5 w-5",
                  isActive && "text-primary",
                  isCompleted && "text-emerald-600",
                  isFailed && "text-red-600"
                )} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <p className="text-sm font-medium text-foreground truncate">
                    {filename}
                  </p>
                  <Badge
                    variant={isFailed ? "destructive" : isCompleted ? "default" : "secondary"}
                    className={cn(
                      "text-xs flex items-center gap-1",
                      isActive && "animate-pulse"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-3 w-3",
                        isActive && "animate-spin"
                      )}
                    />
                    {config.label}
                  </Badge>
                </div>

                {/* Progress Bar */}
                {!isCompleted && (
                  <div className="space-y-1">
                    <Progress value={progressPercent} className="h-1.5" />
                    <p className="text-xs text-muted-foreground">
                      {progressPercent.toFixed(0)}% complete
                    </p>
                  </div>
                )}

                {/* First Glance Summary (when available) */}
                {isCompleted && firstGlance && (
                  <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                    <span>{firstGlance.pages} pages</span>
                    {firstGlance.tables_detected > 0 && (
                      <span>{firstGlance.tables_detected} tables</span>
                    )}
                    {firstGlance.figures_detected > 0 && (
                      <span>{firstGlance.figures_detected} figures</span>
                    )}
                    {confidence && (
                      <Badge variant={confidence === "High" ? "default" : confidence === "Medium" ? "secondary" : "outline"} className="text-xs">
                        {confidence} confidence
                      </Badge>
                    )}
                  </div>
                )}

                {/* Vision Retry Guidance */}
                {isScannedWithVisionOff && (
                  <div className="mt-2 p-2 rounded-md bg-amber-50 border border-amber-200">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
                      <div className="flex-1">
                        <p className="text-xs font-medium text-amber-900 mb-1">
                          Scanned PDF detected
                        </p>
                        <p className="text-xs text-amber-800 mb-2">
                          This PDF appears to be scanned or image-heavy. Vision was OFF during processing, so OCR/figure extraction may be limited.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setShowVisionModal(true)}
                          className="h-6 text-xs border-amber-300 text-amber-700 hover:bg-amber-100"
                        >
                          <Eye className="h-3 w-3 mr-1" />
                          How to enable Vision
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Error Message */}
                {isFailed && error && (
                  <div className="mt-2 p-2 rounded-md bg-red-50 border border-red-200">
                    <p className="text-xs text-red-700 line-clamp-2">
                      {error}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 flex-shrink-0">
              {isFailed && error && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowErrorDialog(true)}
                  className="text-xs"
                >
                  <AlertCircle className="h-3 w-3 mr-1" />
                  View reason
                </Button>
              )}

              {isFailed && onRetry && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onRetry}
                  className="text-xs"
                >
                  <RotateCw className="h-3 w-3 mr-1" />
                  Retry
                </Button>
              )}

              {onRemove && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onRemove}
                  className="text-xs text-muted-foreground hover:text-destructive"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Dialog */}
      <AlertDialog open={showErrorDialog} onOpenChange={setShowErrorDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Ingestion Failed</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p className="font-medium">{filename}</p>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {error || "An unknown error occurred during ingestion."}
              </p>
              {jobId && (
                <p className="text-xs text-muted-foreground mt-2">
                  Job ID: {jobId}
                </p>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Close</AlertDialogCancel>
            {onViewDetails && (
              <AlertDialogAction onClick={onViewDetails}>
                View Details
              </AlertDialogAction>
            )}
            {onRetry && (
              <AlertDialogAction onClick={() => {
                setShowErrorDialog(false)
                onRetry()
              }}>
                Retry
              </AlertDialogAction>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      
      <VisionEnableModal open={showVisionModal} onOpenChange={setShowVisionModal} />
    </>
  )
}

