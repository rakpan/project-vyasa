"use client"

/**
 * Project Creation Wizard - 3-Step Momentum Framing
 * Step 1: Definition (Title, Thesis, RQs)
 * Step 2: Scope (Anti-scope + Templates)
 * Step 3: Rigor (Exploratory/Conservative with live preview)
 */

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { ChevronRight, ChevronLeft, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { toast } from "@/hooks/use-toast"
import { createProject, listProjectTemplates } from "@/services/projectService"
import { PROJECT_TEMPLATES, getTemplateById } from "@/data/project-templates"
import { RigorImpactPreview } from "@/components/rigor-impact-preview"
import type { ProjectCreate, ProjectTemplate } from "@/types/project"

interface WizardState {
  step: 1 | 2 | 3
  title: string
  thesis: string
  research_questions: string[]
  anti_scope: string[]
  rigor_level: "exploratory" | "conservative"
  target_journal: string
}

interface ProjectWizardProps {
  onComplete?: (projectId: string) => void
}

export function ProjectWizard({ onComplete }: ProjectWizardProps) {
  const router = useRouter()
  const [state, setState] = useState<WizardState>({
    step: 1,
    title: "",
    thesis: "",
    research_questions: [],
    anti_scope: [],
    rigor_level: "exploratory",
    target_journal: "",
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [rqInput, setRqInput] = useState("")
  const [antiScopeInput, setAntiScopeInput] = useState("")
  const [selectedTemplate, setSelectedTemplate] = useState<string>("")
  const [templates, setTemplates] = useState<ProjectTemplate[]>(PROJECT_TEMPLATES)
  const [templatesLoading, setTemplatesLoading] = useState(true)

  // Fetch templates from server on mount
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const serverTemplates = await listProjectTemplates()
        if (serverTemplates.length > 0) {
          setTemplates(serverTemplates)
        }
        // If server returns empty or fails, keep static templates
      } catch (error) {
        console.warn("Failed to fetch templates from server, using static fallback:", error)
        // Keep static templates as fallback
      } finally {
        setTemplatesLoading(false)
      }
    }
    fetchTemplates()
  }, [])

  // Apply template when selected
  useEffect(() => {
    if (selectedTemplate) {
      const template = templates.find((t) => t.id === selectedTemplate) || getTemplateById(selectedTemplate)
      if (template) {
        setState((prev) => ({
          ...prev,
          research_questions: [...prev.research_questions, ...template.suggested_rqs].filter(
            (rq, index, self) => self.indexOf(rq) === index // Deduplicate
          ),
          anti_scope: [...prev.anti_scope, ...template.suggested_anti_scope].filter(
            (scope, index, self) => self.indexOf(scope) === index // Deduplicate
          ),
          rigor_level: template.suggested_rigor,
          thesis: prev.thesis || template.example_thesis || prev.thesis,
        }))
      }
    }
  }, [selectedTemplate, templates])

  const canProceedFromStep1 = state.title.trim() !== "" && state.thesis.trim() !== "" && state.research_questions.length > 0
  const canProceedFromStep2 = true // Step 2 is optional
  const canProceedFromStep3 = true // Step 3 always has a selection

  const handleAddRQ = () => {
    const trimmed = rqInput.trim()
    if (trimmed && !state.research_questions.includes(trimmed)) {
      setState((prev) => ({
        ...prev,
        research_questions: [...prev.research_questions, trimmed],
      }))
      setRqInput("")
    }
  }

  const handleRemoveRQ = (rq: string) => {
    setState((prev) => ({
      ...prev,
      research_questions: prev.research_questions.filter((r) => r !== rq),
    }))
  }

  const handleAddAntiScope = () => {
    const trimmed = antiScopeInput.trim()
    if (trimmed && !state.anti_scope.includes(trimmed)) {
      setState((prev) => ({
        ...prev,
        anti_scope: [...prev.anti_scope, trimmed],
      }))
      setAntiScopeInput("")
    }
  }

  const handleRemoveAntiScope = (scope: string) => {
    setState((prev) => ({
      ...prev,
      anti_scope: prev.anti_scope.filter((s) => s !== scope),
    }))
  }

  const handleNext = () => {
    if (state.step === 1 && canProceedFromStep1) {
      setState((prev) => ({ ...prev, step: 2 }))
    } else if (state.step === 2 && canProceedFromStep2) {
      setState((prev) => ({ ...prev, step: 3 }))
    }
  }

  const handleBack = () => {
    if (state.step > 1) {
      setState((prev) => ({ ...prev, step: (prev.step - 1) as 1 | 2 | 3 }))
    }
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      const projectCreate: ProjectCreate = {
        title: state.title,
        thesis: state.thesis,
        research_questions: state.research_questions,
        anti_scope: state.anti_scope.length > 0 ? state.anti_scope : null,
        target_journal: state.target_journal || null,
        seed_files: null,
        rigor_level: state.rigor_level, // Include rigor_level in create payload (atomic)
      }

      const newProject = await createProject(projectCreate)

      // Check if backend returned different rigor_level (reconcile UI state)
      if (newProject.rigor_level && newProject.rigor_level !== state.rigor_level) {
        toast({
          title: "Rigor level adjusted",
          description: `Backend set rigor to "${newProject.rigor_level}" instead of "${state.rigor_level}".`,
          variant: "default",
        })
        // Update local state to match server response (authoritative)
        setState((prev) => ({ ...prev, rigor_level: newProject.rigor_level as "exploratory" | "conservative" }))
      }

      toast({
        title: "Project created",
        description: `"${newProject.title}" has been created successfully.`,
      })

      if (onComplete) {
        onComplete(newProject.id)
      } else {
        router.push(`/projects/${newProject.id}`)
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to create project"
      toast({
        title: "Project creation failed",
        description: errorMessage,
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Stepper */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {[1, 2, 3].map((stepNum) => (
            <div key={stepNum} className="flex items-center flex-1">
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors ${
                  state.step === stepNum
                    ? "border-primary bg-primary text-primary-foreground"
                    : state.step > stepNum
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-muted bg-background text-muted-foreground"
                }`}
              >
                {stepNum}
              </div>
              {stepNum < 3 && (
                <div
                  className={`flex-1 h-0.5 mx-2 transition-colors ${
                    state.step > stepNum ? "bg-primary" : "bg-muted"
                  }`}
                />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-between mt-2 text-sm text-muted-foreground">
          <span>Definition</span>
          <span>Scope</span>
          <span>Rigor</span>
        </div>
      </div>

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>
            {state.step === 1 && "Project Definition"}
            {state.step === 2 && "Scope & Templates"}
            {state.step === 3 && "Rigor Level"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Step 1: Definition */}
          {state.step === 1 && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">
                  Title <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="title"
                  value={state.title}
                  onChange={(e) => setState((prev) => ({ ...prev, title: e.target.value }))}
                  placeholder="e.g., Security Analysis of Web Applications"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="thesis">
                  Thesis <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="thesis"
                  value={state.thesis}
                  onChange={(e) => setState((prev) => ({ ...prev, thesis: e.target.value }))}
                  placeholder="The core argument or hypothesis..."
                  rows={4}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="research_questions">
                  Research Questions <span className="text-destructive">*</span>
                </Label>
                <div className="flex gap-2">
                  <Input
                    id="research_questions"
                    value={rqInput}
                    onChange={(e) => setRqInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault()
                        handleAddRQ()
                      }
                    }}
                    placeholder="Enter a research question and press Enter"
                  />
                  <Button type="button" onClick={handleAddRQ} disabled={!rqInput.trim()}>
                    Add
                  </Button>
                </div>
                {state.research_questions.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {state.research_questions.map((rq) => (
                      <Badge key={rq} variant="secondary" className="gap-1">
                        {rq}
                        <X
                          className="h-3 w-3 cursor-pointer"
                          onClick={() => handleRemoveRQ(rq)}
                        />
                      </Badge>
                    ))}
                  </div>
                )}
                {state.research_questions.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    At least one research question is required
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Step 2: Scope */}
          {state.step === 2 && (
            <div className="space-y-6">
              <div className="space-y-2">
                <Label>Templates (Optional)</Label>
                <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a template to pre-fill fields..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">None (Start from scratch)</SelectItem>
                    {templatesLoading ? (
                      <SelectItem value="" disabled>Loading templates...</SelectItem>
                    ) : (
                      templates.map((template) => (
                        <SelectItem key={template.id} value={template.id}>
                          {template.name} - {template.description}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                {selectedTemplate && (
                  <p className="text-xs text-muted-foreground">
                    Template applied. You can edit the fields below.
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="anti_scope">Anti-Scope (Optional)</Label>
                <p className="text-xs text-muted-foreground mb-2">
                  Explicitly out-of-scope topics. These help focus the research.
                </p>
                <div className="flex gap-2">
                  <Input
                    id="anti_scope"
                    value={antiScopeInput}
                    onChange={(e) => setAntiScopeInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault()
                        handleAddAntiScope()
                      }
                    }}
                    placeholder="Enter an out-of-scope topic and press Enter"
                  />
                  <Button
                    type="button"
                    onClick={handleAddAntiScope}
                    disabled={!antiScopeInput.trim()}
                  >
                    Add
                  </Button>
                </div>
                {state.anti_scope.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {state.anti_scope.map((scope) => (
                      <Badge key={scope} variant="outline" className="gap-1">
                        {scope}
                        <X
                          className="h-3 w-3 cursor-pointer"
                          onClick={() => handleRemoveAntiScope(scope)}
                        />
                      </Badge>
                    ))}
                  </div>
                )}
                {state.anti_scope.length === 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    <Badge variant="outline" className="opacity-50">
                      Example: Hardware security
                    </Badge>
                    <Badge variant="outline" className="opacity-50">
                      Example: Social engineering
                    </Badge>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="target_journal">Target Journal (Optional)</Label>
                <Input
                  id="target_journal"
                  value={state.target_journal}
                  onChange={(e) =>
                    setState((prev) => ({ ...prev, target_journal: e.target.value }))
                  }
                  placeholder="e.g., IEEE Security & Privacy"
                />
              </div>
            </div>
          )}

          {/* Step 3: Rigor */}
          {state.step === 3 && (
            <div className="space-y-6">
              <div className="space-y-2">
                <Label>Rigor Level</Label>
                <Select
                  value={state.rigor_level}
                  onValueChange={(value: "exploratory" | "conservative") =>
                    setState((prev) => ({ ...prev, rigor_level: value }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="exploratory">Exploratory</SelectItem>
                    <SelectItem value="conservative">Conservative</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Exploratory: Flexible, allows general artifacts. Conservative: Strict validation,
                  requires explicit RQ links.
                </p>
              </div>

              {/* Rigor Impact Preview */}
              <RigorImpactPreview rigorLevel={state.rigor_level} />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex justify-between mt-6">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={state.step === 1 || isSubmitting}
        >
          <ChevronLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        {state.step < 3 ? (
          <Button
            onClick={handleNext}
            disabled={
              (state.step === 1 && !canProceedFromStep1) ||
              (state.step === 2 && !canProceedFromStep2) ||
              isSubmitting
            }
          >
            Next
            <ChevronRight className="h-4 w-4 ml-2" />
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Creating..." : "Create Project"}
          </Button>
        )}
      </div>
    </div>
  )
}

