"use client"

/**
 * Manuscript Lab - Right Pane (33% width)
 * Project intent accordion and drafting area
 */

import { useState } from "react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Download, FileText } from "lucide-react"
import { useProjectStore } from "@/state/useProjectStore"

interface ManuscriptLabProps {
  projectId: string
}

export function ManuscriptLab({ projectId }: ManuscriptLabProps) {
  const { activeProject } = useProjectStore()
  const [isExporting, setIsExporting] = useState(false)

  const handleExport = async () => {
    setIsExporting(true)
    // TODO: Implement export functionality
    setTimeout(() => setIsExporting(false), 1000)
  }

  if (!activeProject) {
    return (
      <div className="flex flex-col h-full p-4">
        <p className="text-sm text-muted-foreground">Loading project...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Intent Accordion (Top) */}
      <div className="flex-shrink-0 border-b border-slate-200">
        <Accordion type="single" collapsible defaultValue="" className="w-full">
          <AccordionItem value="intent" className="border-0">
            <AccordionTrigger className="px-4 py-3 text-sm font-semibold hover:no-underline">
              Project Intent
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="space-y-4">
                {/* Thesis */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Thesis
                  </p>
                  <p className="text-sm leading-relaxed">{activeProject.thesis}</p>
                </div>

                {/* Research Questions */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Research Questions
                  </p>
                  <ul className="space-y-2">
                    {activeProject.research_questions.map((rq, idx) => (
                      <li key={idx} className="text-sm flex items-start gap-2">
                        <span className="text-muted-foreground mt-1">•</span>
                        <span className="flex-1">{rq}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Anti-Scope */}
                {activeProject.anti_scope && activeProject.anti_scope.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                      Anti-Scope
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {activeProject.anti_scope.map((item, idx) => (
                        <Badge key={idx} variant="outline" className="text-xs">
                          {item}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Target Journal */}
                {activeProject.target_journal && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                      Target Journal
                    </p>
                    <Badge variant="secondary" className="text-xs">
                      {activeProject.target_journal}
                    </Badge>
                  </div>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>

      {/* Drafting Area (Main) */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <CardTitle className="text-sm font-semibold">Manuscript Draft</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={isExporting}
            className="h-7 text-xs"
          >
            <Download className="h-3 w-3 mr-1" />
            Export
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto bg-slate-50 p-4">
          <div className="bg-white shadow-sm min-h-full rounded border border-slate-200 p-6">
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <FileText className="h-8 w-8 text-slate-400" />
              </div>
              <h3 className="text-sm font-semibold mb-2">Manuscript Editor</h3>
              <p className="text-xs text-muted-foreground max-w-xs">
                Text editor and block-based manuscript composition coming soon.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

