"use client"

import { useEffect, useState } from "react"
import { Save, CheckCircle2, XCircle, RotateCcw, AlertCircle, Clock, ChevronDown, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { toast } from "@/hooks/use-toast"

const PROMPT_IDS = [
  { id: "critic_verify", label: "Critic Verify" },
  { id: "cartographer_pass2", label: "Cartographer Pass 2" },
  { id: "synthesizer_section_writer", label: "Synthesizer Section Writer" },
  { id: "lead_counsel_policy", label: "Lead Counsel Policy" },
]

const PLACEHOLDERS = [
  { var: "{{project_context}}", desc: "Project configuration (thesis, RQs)" },
  { var: "{{evidence_pack}}", desc: "Evidence Pack snippets (Packet A)" },
  { var: "{{analytical_notes}}", desc: "Analytical Notes (Packet B)" },
  { var: "{{section_metadata}}", desc: "Section heading, journal_slot, depth_intent" },
  { var: "{{citation_format}}", desc: "Citation token format (e.g., \\cite{chunk:<id>})" },
]

interface PromptProfile {
  prompt_id: string
  version: number
  template: string
  output_type: "json" | "markdown"
  required_fields: string[]
  constraints: {
    citation_token_format?: string
    bounded_retry?: boolean
    packet_a_facts_only?: boolean
  }
  created_at?: string | null
  created_by?: string | null
  validation_status?: string | null
  validation_timestamp?: string | null
  validation_errors?: string[]
}

interface ActivePromptSet {
  active_versions: Record<string, number>
  updated_at?: string
}

export function PromptProfilesTab() {
  const [selectedPromptId, setSelectedPromptId] = useState<string>("critic_verify")
  const [profiles, setProfiles] = useState<PromptProfile[]>([])
  const [activeVersions, setActiveVersions] = useState<Record<string, number>>({})
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)
  const [template, setTemplate] = useState("")
  const [outputType, setOutputType] = useState<"json" | "markdown">("markdown")
  const [requiredFields, setRequiredFields] = useState<string[]>([])
  const [validationResult, setValidationResult] = useState<{ valid: boolean; errors: string[]; warnings?: string[] } | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isValidating, setIsValidating] = useState(false)
  const [errorsExpanded, setErrorsExpanded] = useState(false)

  useEffect(() => {
    loadActiveVersions()
  }, [])

  useEffect(() => {
    if (selectedPromptId) {
      loadProfiles(selectedPromptId)
    }
  }, [selectedPromptId])

  useEffect(() => {
    if (selectedVersion !== null && profiles.length > 0) {
      const profile = profiles.find((p) => p.version === selectedVersion)
      if (profile) {
        setTemplate(profile.template)
        setOutputType(profile.output_type)
        setRequiredFields(profile.required_fields || [])
        setValidationResult(null)
        setErrorsExpanded(false) // Reset errors panel when switching versions
      }
    }
  }, [selectedVersion, profiles])

  const loadActiveVersions = async () => {
    try {
      // Load all prompts to get active versions
      const response = await fetch("/api/proxy/orchestrator/api/settings/prompts")
      if (response.ok) {
        const data: PromptProfile[] = await response.json()
        // Group by prompt_id and find active version (we'll use latest as fallback)
        // In a real implementation, we'd query active_prompt_set, but for now use latest
        const active: Record<string, number> = {}
        data.forEach((p) => {
          if (!active[p.prompt_id] || p.version > active[p.prompt_id]) {
            active[p.prompt_id] = p.version
          }
        })
        setActiveVersions(active)
      }
    } catch (error) {
      console.error("Failed to load active versions:", error)
    }
  }

  const loadProfiles = async (promptId: string) => {
    try {
      setIsLoading(true)
      const response = await fetch(`/api/proxy/orchestrator/api/settings/prompts?prompt_id=${promptId}`)
      if (response.ok) {
        const data: PromptProfile[] = await response.json()
        setProfiles(data.sort((a, b) => b.version - a.version))
        if (data.length > 0) {
          const activeVersion = activeVersions[promptId] || data[0].version
          setSelectedVersion(activeVersion)
        }
      }
    } catch (error) {
      console.error("Failed to load profiles:", error)
      toast({
        title: "Error",
        description: "Failed to load prompt profiles.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleValidate = async () => {
    try {
      setIsValidating(true)
      const response = await fetch("/api/proxy/orchestrator/api/settings/prompts/validate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          template,
          output_type: outputType,
          required_fields: outputType === "json" ? requiredFields : [],
          prompt_id: selectedPromptId,  // Include to update validation status
          version: selectedVersion,  // Include to update validation status
        }),
      })

      if (response.ok) {
        const result = await response.json()
        // Update UI state immediately
        setValidationResult(result)
        
        // Reload profiles to get updated validation status from backend
        if (selectedPromptId && selectedVersion) {
          await loadProfiles(selectedPromptId)
          // Ensure selected version is still selected after reload
          setSelectedVersion(selectedVersion)
        }
        
        if (result.valid) {
          toast({
            title: "Validation passed",
            description: result.warnings?.length 
              ? `Template is valid. Warnings: ${result.warnings.join("; ")}`
              : "Template is valid and ready to activate.",
          })
        } else {
          toast({
            title: "Validation failed",
            description: result.errors.join(", "),
            variant: "destructive",
          })
        }
        
        // Show warnings if any
        if (result.warnings && result.warnings.length > 0) {
          toast({
            title: "Validation warnings",
            description: result.warnings.join("; "),
            variant: "default",
          })
        }
      } else {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || "Validation failed")
      }
    } catch (error) {
      console.error("Failed to validate:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to validate template.",
        variant: "destructive",
      })
    } finally {
      setIsValidating(false)
    }
  }

  const handleSaveDraft = async () => {
    try {
      setIsSaving(true)
      const response = await fetch("/api/proxy/orchestrator/api/settings/prompts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt_id: selectedPromptId,
          template,
          output_type: outputType,
          required_fields: outputType === "json" ? requiredFields : [],
        }),
      })

      if (response.ok) {
        const newProfile: PromptProfile = await response.json()
        toast({
          title: "Saved",
          description: `Created version ${newProfile.version} of ${selectedPromptId}.`,
        })
        await loadProfiles(selectedPromptId)
        setSelectedVersion(newProfile.version)
        setValidationResult(null)
      } else {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || "Failed to save")
      }
    } catch (error) {
      console.error("Failed to save:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to save prompt profile.",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleActivate = async () => {
    if (selectedVersion === null) return

    try {
      setIsSaving(true)
      const response = await fetch("/api/proxy/orchestrator/api/settings/prompts/activate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt_id: selectedPromptId,
          version: selectedVersion,
        }),
      })

      if (response.ok) {
        await loadActiveVersions()
        await loadProfiles(selectedPromptId)  // Reload to refresh active status
        toast({
          title: "Activated",
          description: `Version ${selectedVersion} is now active.`,
        })
      } else {
        const errorData = await response.json().catch(() => ({}))
        const errorMsg = errorData.error || "Failed to activate"
        
        // Check if it's a validation error
        if (errorData.code === "VALIDATION_FAILED" || response.status === 400) {
          toast({
            title: "Cannot activate",
            description: errorMsg,
            variant: "destructive",
          })
        } else {
          throw new Error(errorMsg)
        }
      }
    } catch (error) {
      console.error("Failed to activate:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to activate version.",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleRollback = async () => {
    if (profiles.length < 2) {
      toast({
        title: "No previous version",
        description: "Cannot rollback: only one version exists.",
        variant: "destructive",
      })
      return
    }

    const previousVersion = profiles.find((p) => p.version < (selectedVersion || 0))
    if (!previousVersion) {
      toast({
        title: "No previous version",
        description: "Cannot rollback: no older version found.",
        variant: "destructive",
      })
      return
    }

    try {
      setIsSaving(true)
      const response = await fetch("/api/proxy/orchestrator/api/settings/prompts/activate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt_id: selectedPromptId,
          version: previousVersion.version,
        }),
      })

      if (response.ok) {
        await loadActiveVersions()
        setSelectedVersion(previousVersion.version)
        toast({
          title: "Rolled back",
          description: `Activated version ${previousVersion.version}.`,
        })
      } else {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || "Failed to rollback")
      }
    } catch (error) {
      console.error("Failed to rollback:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to rollback version.",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  const activeVersion = activeVersions[selectedPromptId] || null
  const isActiveVersion = selectedVersion !== null && selectedVersion === activeVersion
  
  // Check if selected profile has valid validation status (type-safe)
  const selectedProfile: PromptProfile | undefined = profiles.find((p) => p.version === selectedVersion)
  const hasValidValidation = selectedProfile?.validation_status === "valid"
  const validationAge: number | null = selectedProfile?.validation_timestamp
    ? (Date.now() - new Date(selectedProfile.validation_timestamp).getTime()) / (1000 * 60)  // minutes
    : null
  const isValidationStale = validationAge !== null && validationAge > 30
  
  // Format validation timestamp for display
  const formatValidationTimestamp = (timestamp: string | null | undefined): string | null => {
    if (!timestamp) return null
    try {
      const date = new Date(timestamp)
      return date.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    } catch {
      return null
    }
  }
  
  // Get validation status badge variant
  const getValidationBadgeVariant = (status: string | null | undefined): "default" | "destructive" | "secondary" => {
    if (status === "valid") return "default"
    if (status === "invalid") return "destructive"
    return "secondary"
  }
  
  // Get validation status label
  const getValidationStatusLabel = (status: string | null | undefined): string => {
    if (status === "valid") return "Validated"
    if (status === "invalid") return "Invalid"
    return "Not validated"
  }
  
  // Can activate if: validation passed AND not stale AND (validation result shows valid OR profile shows valid)
  const canActivate = 
    (validationResult?.valid === true || hasValidValidation) && 
    !isValidationStale &&
    selectedVersion !== null

  return (
    <div className="grid grid-cols-3 gap-6">
      {/* Left: Prompt Selector */}
      <Card>
        <CardHeader>
          <CardTitle>Prompt Profiles</CardTitle>
          <CardDescription>Select a prompt to edit</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Prompt ID</Label>
            <Select value={selectedPromptId} onValueChange={setSelectedPromptId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROMPT_IDS.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading ? (
            <div className="text-sm text-muted-foreground">Loading versions...</div>
          ) : profiles.length === 0 ? (
            <div className="text-sm text-muted-foreground">No versions found</div>
          ) : (
            <div>
              <Label>Version</Label>
              <Select
                value={selectedVersion?.toString() || ""}
                onValueChange={(v) => setSelectedVersion(parseInt(v))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {profiles.map((p) => {
                    const isActive = p.version === activeVersion
                    const validationStatus: string | null = p.validation_status ?? null
                    return (
                      <SelectItem key={p.version} value={p.version.toString()}>
                        <div className="flex items-center justify-between w-full gap-2">
                          <span className="flex-1">
                            v{p.version} {isActive && <span className="text-muted-foreground">(Active)</span>}
                          </span>
                          <Badge 
                            variant={getValidationBadgeVariant(validationStatus)}
                            className="text-xs shrink-0"
                          >
                            {getValidationStatusLabel(validationStatus)}
                          </Badge>
                        </div>
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
              {activeVersion && (
                <div className="mt-2 text-xs text-muted-foreground">
                  Active: v{activeVersion}
                </div>
              )}
            </div>
          )}

          {/* Placeholders Help */}
          <div className="mt-6 pt-4 border-t">
            <Label className="text-xs font-semibold mb-2 block">Template Placeholders</Label>
            <div className="space-y-1 text-xs text-muted-foreground">
              {PLACEHOLDERS.map((p) => (
                <div key={p.var}>
                  <code className="text-xs bg-muted px-1 rounded">{p.var}</code>
                  <div className="ml-2 text-xs">{p.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Right: Editor */}
      <Card className="col-span-2">
        <CardHeader>
          <CardTitle>Template Editor</CardTitle>
          <CardDescription>
            Edit the prompt template. Use Save Draft to create a new version, then Validate and Activate.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Validation Status Panel */}
          {selectedProfile && (
            <div className="border rounded-md p-4 bg-muted/30">
              <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Label className="text-sm font-semibold">Validation Status</Label>
                  <Badge variant={getValidationBadgeVariant(selectedProfile.validation_status ?? null)}>
                    {getValidationStatusLabel(selectedProfile.validation_status ?? null)}
                  </Badge>
                </div>
                {selectedProfile.validation_timestamp && (
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <span>Last validated: {formatValidationTimestamp(selectedProfile.validation_timestamp) ?? "Unknown"}</span>
                    {validationAge !== null && (
                      <span className="ml-1">
                        ({Math.round(validationAge)} min ago)
                      </span>
                    )}
                  </div>
                )}
              </div>
              
              {/* Validation Errors (if any) */}
              {selectedProfile.validation_errors && selectedProfile.validation_errors.length > 0 && (
                <Collapsible open={errorsExpanded} onOpenChange={setErrorsExpanded}>
                  <CollapsibleTrigger className="flex items-center gap-2 text-sm text-destructive hover:text-destructive/80 mt-2">
                    {errorsExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                    <span>View {selectedProfile.validation_errors.length} error{selectedProfile.validation_errors.length !== 1 ? "s" : ""}</span>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="mt-2 pl-6">
                    <ul className="list-disc space-y-1 text-sm text-destructive">
                      {selectedProfile.validation_errors.map((error, i) => (
                        <li key={i}>{error}</li>
                      ))}
                    </ul>
                  </CollapsibleContent>
                </Collapsible>
              )}
              
              {/* Stale validation warning */}
              {isValidationStale && hasValidValidation && (
                <Alert variant="default" className="mt-2">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-sm">
                    Validation is stale (older than 30 minutes). Please re-validate before activation.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}
          
          {/* Current Validation Result (from Validate action) */}
          {validationResult && (
            <Alert variant={validationResult.valid ? "default" : "destructive"}>
              {validationResult.valid ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              <AlertDescription>
                {validationResult.valid ? (
                  <div>
                    <div className="font-semibold">Template is valid</div>
                    {validationResult.warnings && validationResult.warnings.length > 0 && (
                      <div className="mt-2 text-sm">
                        <div className="font-semibold">Warnings:</div>
                        <ul className="list-disc list-inside mt-1">
                          {validationResult.warnings.map((w, i) => (
                            <li key={i}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className="font-semibold">Validation errors:</div>
                    <ul className="list-disc list-inside mt-1">
                      {validationResult.errors.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}

          <div>
            <Label htmlFor="output_type">Output Type</Label>
            <Select value={outputType} onValueChange={(v) => setOutputType(v as "json" | "markdown")}>
              <SelectTrigger id="output_type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="json">JSON</SelectItem>
                <SelectItem value="markdown">Markdown</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {outputType === "json" && (
            <div>
              <Label htmlFor="required_fields">Required Fields (comma-separated)</Label>
              <input
                id="required_fields"
                type="text"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={requiredFields.join(", ")}
                onChange={(e) =>
                  setRequiredFields(
                    e.target.value
                      .split(",")
                      .map((f) => f.trim())
                      .filter((f) => f)
                  )
                }
                placeholder="decision, rationale, supporting_chunk_ids"
              />
            </div>
          )}

          <div>
            <Label htmlFor="template">Template</Label>
            <Textarea
              id="template"
              className="font-mono text-sm min-h-[400px]"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              placeholder="Enter prompt template..."
            />
          </div>

          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={handleValidate}
              disabled={isValidating || !template}
            >
              {isValidating ? "Validating..." : "Validate"}
            </Button>
            <Button
              variant="outline"
              onClick={handleSaveDraft}
              disabled={isSaving || !template}
            >
              <Save className="h-4 w-4 mr-2" />
              {isSaving ? "Saving..." : "Save Draft"}
            </Button>
            <Button
              onClick={handleActivate}
              disabled={isSaving || !canActivate || isActiveVersion}
              title={
                !canActivate && !isActiveVersion
                  ? isValidationStale
                    ? "Validation is stale (>30 minutes). Please re-validate."
                    : !hasValidValidation && !validationResult?.valid
                    ? "Template must be validated before activation."
                    : "Cannot activate"
                  : undefined
              }
            >
              {isActiveVersion ? "Active" : "Activate"}
            </Button>
            <Button
              variant="outline"
              onClick={handleRollback}
              disabled={isSaving || profiles.length < 2 || !isActiveVersion}
            >
              <RotateCcw className="h-4 w-4 mr-2" />
              Rollback
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
