//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { FileText, Upload, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useRouter } from "next/navigation"
import { useProjectStore } from "@/state/useProjectStore"

/**
 * Empty State for Workbench when no PDF is uploaded
 * Explains the 2-pane fallback layout
 */
export function EmptyStateWorkbench() {
  const router = useRouter()
  const { activeProjectId } = useProjectStore()

  const handleUpload = () => {
    if (activeProjectId) {
      router.push(`/projects/${activeProjectId}?tab=upload`)
    } else {
      router.push("/projects")
    }
  }

  return (
    <div className="h-full flex items-center justify-center p-8">
      <Card className="max-w-md w-full border-slate-200">
        <CardHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-12 w-12 rounded-lg bg-slate-100 flex items-center justify-center">
              <FileText className="h-6 w-6 text-slate-600" />
            </div>
            <div>
              <CardTitle className="text-lg">No Source Document</CardTitle>
              <CardDescription className="text-sm">
                Upload a PDF to begin research analysis
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>
              The workbench uses a <strong>2-pane layout</strong> when no PDF is available:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>
                <strong>Left:</strong> Synthesis/Editor for manuscript composition
              </li>
              <li>
                <strong>Right:</strong> Context/Graph for knowledge visualization
              </li>
            </ul>
            <p className="pt-2">
              Once you upload a PDF, a third pane appears on the left for source document viewing and evidence verification.
            </p>
          </div>

          <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <Info className="h-4 w-4 text-blue-600 shrink-0" />
            <p className="text-xs text-blue-900">
              <strong>Tip:</strong> You can also process raw text without a PDF. The system will extract knowledge directly from the text input.
            </p>
          </div>

          <Button onClick={handleUpload} className="w-full" size="sm">
            <Upload className="h-4 w-4 mr-2" />
            Upload Document
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

