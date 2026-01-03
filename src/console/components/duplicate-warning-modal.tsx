"use client"

/**
 * Duplicate Warning Modal Component
 * Shows when a file duplicate is detected, listing matching projects
 */

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { AlertTriangle } from "lucide-react"

interface DuplicateMatch {
  project_id: string
  project_title: string
  ingested_at: string
}

interface DuplicateWarningModalProps {
  open: boolean
  filename: string
  matches: DuplicateMatch[]
  onProceed: () => void
  onCancel: () => void
}

export function DuplicateWarningModal({
  open,
  filename,
  matches,
  onProceed,
  onCancel,
}: DuplicateWarningModalProps) {
  return (
    <AlertDialog open={open} onOpenChange={(isOpen) => !isOpen && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Duplicate File Detected
          </AlertDialogTitle>
          <AlertDialogDescription className="space-y-2">
            <p>
              The file <strong>{filename}</strong> has already been ingested in the following project(s):
            </p>
            <ul className="list-disc list-inside space-y-1 text-sm">
              {matches.map((match, idx) => (
                <li key={idx}>
                  <strong>{match.project_title}</strong>
                  {match.ingested_at && (
                    <span className="text-muted-foreground ml-2">
                      (ingested {new Date(match.ingested_at).toLocaleDateString()})
                    </span>
                  )}
                </li>
              ))}
            </ul>
            <p className="text-sm text-muted-foreground mt-2">
              Do you want to proceed with uploading this file anyway?
            </p>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onProceed}>Proceed Anyway</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

