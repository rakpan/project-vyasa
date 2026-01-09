"use client"

/**
 * Blueprint Tab
 * 
 * Paste mode (YAML/JSON) for manuscript blueprint
 * Save + last saved timestamp
 * Preview parsed sections list
 */

import { useState, useEffect, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { toast } from "@/hooks/use-toast"
import { Loader2, Save, CheckCircle2, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface BlueprintTabProps {
  projectId: string
}

interface BlueprintSection {
  section_id: string
  heading: string
  journal_slot: string
  linked_rqs: string[]
  depth_intent: string
}

interface Blueprint {
  blueprint_id: string
  project_id: string
  title: string
  sections: BlueprintSection[]
  created_at: string
  updated_at: string
}

export function BlueprintTab({ projectId }: BlueprintTabProps) {
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [yamlText, setYamlText] = useState("")
  const [parseError, setParseError] = useState<string | null>(null)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)

  // Fetch blueprint
  useEffect(() => {
    const fetchBlueprint = async () => {
      setIsLoading(true)
      try {
        const response = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/blueprint`)
        if (!response.ok) {
          if (response.status === 404) {
            // No blueprint yet - start with empty
            setYamlText("")
            setBlueprint(null)
            return
          }
          throw new Error(`Failed to fetch blueprint: ${response.status}`)
        }
        const data = await response.json()
        // API returns direct blueprint object: {blueprint_id, sections, ...}
        setBlueprint(data)
        
        // Convert blueprint to JSON for editing
        if (data) {
          const json = blueprintToYaml(data)
          setYamlText(json)
          if (data.updated_at) {
            setLastSaved(new Date(data.updated_at))
          }
        }
      } catch (error) {
        console.error("Failed to fetch blueprint:", error)
        toast({
          title: "Error",
          description: "Failed to load blueprint",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
      }
    }

    if (projectId) {
      fetchBlueprint()
    }
  }, [projectId])

  // Parse YAML/JSON and validate
  useEffect(() => {
    if (!yamlText.trim()) {
      setParseError(null)
      return
    }

    try {
      // Try parsing as YAML or JSON
      let parsed: any
      if (yamlText.trim().startsWith("{")) {
        // JSON
        parsed = JSON.parse(yamlText)
      } else {
        // Try YAML (basic parsing - in production, use a YAML library)
        // For now, we'll accept JSON format
        try {
          parsed = JSON.parse(yamlText)
        } catch {
          // Simple YAML-like structure parsing
          // This is a basic implementation - in production, use js-yaml
          setParseError("YAML parsing not fully supported. Please use JSON format.")
          return
        }
      }

      // Validate structure
      if (!parsed.sections || !Array.isArray(parsed.sections)) {
        setParseError("Blueprint must have 'sections' array")
        return
      }

      // Validate sections
      for (const section of parsed.sections) {
        if (!section.heading || !section.journal_slot) {
          setParseError("Each section must have 'heading' and 'journal_slot'")
          return
        }
      }

      setParseError(null)
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Invalid format")
    }
  }, [yamlText])

  // Convert blueprint to YAML-like string
  const blueprintToYaml = (bp: Blueprint): string => {
    const obj = {
      title: bp.title,
      sections: bp.sections.map((s) => ({
        heading: s.heading,
        journal_slot: s.journal_slot,
        linked_rqs: s.linked_rqs || [],
        depth_intent: s.depth_intent || "proof",
      })),
    }
    return JSON.stringify(obj, null, 2)
  }

  // Parse sections for preview
  const parsedSections = useMemo(() => {
    if (!yamlText.trim() || parseError) return []

    try {
      const parsed = JSON.parse(yamlText)
      return parsed.sections || []
    } catch {
      return []
    }
  }, [yamlText, parseError])

  // Save blueprint
  const handleSave = async () => {
    if (!yamlText.trim()) {
      toast({
        title: "Error",
        description: "Blueprint cannot be empty",
        variant: "destructive",
      })
      return
    }

    if (parseError) {
      toast({
        title: "Error",
        description: "Please fix parsing errors before saving",
        variant: "destructive",
      })
      return
    }

    setIsSaving(true)
    try {
      const parsed = JSON.parse(yamlText)
      
      const response = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/blueprint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: parsed.title,
          sections: parsed.sections,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `Failed to save blueprint: ${response.status}`)
      }

      const data = await response.json()
      // API returns direct blueprint object: {blueprint_id, title, sections, ...}
      setBlueprint(data)
      setLastSaved(new Date())
      
      // Update editor with saved blueprint (in case server added fields)
      const updatedJson = blueprintToYaml(data)
      setYamlText(updatedJson)
      
      toast({
        title: "Success",
        description: "Blueprint saved successfully",
      })
    } catch (error) {
      console.error("Failed to save blueprint:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to save blueprint",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex-1 flex gap-4 min-h-0">
      {/* Left: Editor */}
      <div className="flex-1 flex flex-col border rounded-lg">
        <CardHeader className="border-b">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-sm">Blueprint Editor</CardTitle>
              <CardDescription className="text-xs mt-1">
                Paste YAML/JSON blueprint structure
              </CardDescription>
            </div>
            {lastSaved && (
              <div className="text-xs text-muted-foreground">
                Last saved: {lastSaved.toLocaleString()}
              </div>
            )}
          </div>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col p-4 min-h-0">
          <div className="flex-1 flex flex-col min-h-0 mb-4">
            <Label htmlFor="blueprint-yaml" className="text-xs font-semibold mb-2">
              Blueprint (JSON format)
            </Label>
            <Textarea
              id="blueprint-yaml"
              value={yamlText}
              onChange={(e) => setYamlText(e.target.value)}
              placeholder={`{
  "sections": [
    {
      "heading": "Introduction",
      "journal_slot": "introduction",
      "linked_rqs": ["RQ1"],
      "depth_intent": "hook"
    },
    {
      "heading": "Methods",
      "journal_slot": "methods",
      "linked_rqs": ["RQ2"],
      "depth_intent": "proof"
    }
  ],
  "target_journal": "Optional journal name"
}`}
              className="flex-1 font-mono text-xs min-h-[400px]"
            />
          </div>

          {parseError && (
            <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-semibold text-destructive">Parse Error</p>
                  <p className="text-xs text-destructive/80 mt-1">{parseError}</p>
                </div>
              </div>
            </div>
          )}

          {!parseError && yamlText.trim() && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-semibold text-green-800">Valid</p>
                  <p className="text-xs text-green-700 mt-1">
                    {parsedSections.length} section{parsedSections.length !== 1 ? "s" : ""} parsed
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={isSaving || !!parseError || !yamlText.trim()}>
              {isSaving ? (
                <>
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-3 w-3 mr-1" />
                  Save Blueprint
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </div>

      {/* Right: Preview */}
      <div className="w-1/3 flex flex-col border rounded-lg">
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Sections Preview</CardTitle>
          <CardDescription className="text-xs mt-1">
            Parsed sections from blueprint
          </CardDescription>
        </CardHeader>

        <CardContent className="flex-1 p-4 min-h-0">
          <ScrollArea className="h-full">
            {!yamlText.trim() ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                Enter blueprint to see preview
              </div>
            ) : parseError ? (
              <div className="text-center py-8 text-sm text-destructive">
                Fix errors to see preview
              </div>
            ) : parsedSections.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                No sections found
              </div>
            ) : (
              <div className="space-y-3">
                {parsedSections.map((section: any, idx: number) => (
                  <Card key={idx} className="p-3">
                    <div className="space-y-2">
                      <div className="flex items-start justify-between">
                        <h4 className="text-sm font-semibold">{section.heading || `Section ${idx + 1}`}</h4>
                        <Badge variant="outline" className="text-[10px]">
                          {section.journal_slot || "N/A"}
                        </Badge>
                      </div>
                      {section.linked_rqs && section.linked_rqs.length > 0 && (
                        <div className="text-xs text-muted-foreground">
                          RQs: {section.linked_rqs.join(", ")}
                        </div>
                      )}
                      {section.depth_intent && (
                        <div className="text-xs text-muted-foreground">
                          Intent: <Badge variant="secondary" className="text-[10px] ml-1">
                            {section.depth_intent}
                          </Badge>
                        </div>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </div>
    </div>
  )
}
