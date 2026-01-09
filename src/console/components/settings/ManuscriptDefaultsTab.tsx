"use client"

import { useEffect, useState } from "react"
import { Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { toast } from "@/hooks/use-toast"

interface ManuscriptDefaults {
  word_limit_total: number
  abstract_word_limit: number
  abstract_char_limit: number
  max_tables: number
  max_figures: number
  citation_style: {
    numeric_superscript: boolean
    order_of_appearance: boolean
  }
  locking_defaults: {
    locked_sections_immutable: boolean
    allow_citation_reindexing_without_text_change: boolean
  }
}

export function ManuscriptDefaultsTab() {
  const [defaults, setDefaults] = useState<ManuscriptDefaults | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      setIsLoading(true)
      const response = await fetch("/api/proxy/orchestrator/api/settings")
      if (response.ok) {
        const data = await response.json()
        setDefaults(data.manuscript_defaults || null)
      } else {
        toast({
          title: "Failed to load settings",
          description: "Could not load manuscript defaults. Using defaults.",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error("Failed to load settings:", error)
      toast({
        title: "Error",
        description: "Failed to load manuscript default settings.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    if (!defaults) return

    try {
      setIsSaving(true)
      const response = await fetch("/api/proxy/orchestrator/api/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          manuscript_defaults: defaults,
        }),
      })

      if (response.ok) {
        toast({
          title: "Saved",
          description: "Manuscript default settings saved successfully.",
        })
      } else {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || "Failed to save settings")
      }
    } catch (error) {
      console.error("Failed to save settings:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to save manuscript default settings.",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading || !defaults) {
    return <div className="text-center py-8 text-muted-foreground">Loading...</div>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manuscript Defaults</CardTitle>
        <CardDescription>
          Configure default limits and formatting options for manuscript generation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Word Limits */}
        <div>
          <h3 className="text-lg font-semibold mb-4">Word Limits</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="word_limit_total">Total Word Limit</Label>
              <Input
                id="word_limit_total"
                type="number"
                min="1000"
                max="50000"
                value={defaults.word_limit_total}
                onChange={(e) =>
                  setDefaults({
                    ...defaults,
                    word_limit_total: parseInt(e.target.value) || 8000,
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="abstract_word_limit">Abstract Word Limit</Label>
              <Input
                id="abstract_word_limit"
                type="number"
                min="100"
                max="500"
                value={defaults.abstract_word_limit}
                onChange={(e) =>
                  setDefaults({
                    ...defaults,
                    abstract_word_limit: parseInt(e.target.value) || 250,
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="abstract_char_limit">Abstract Character Limit</Label>
              <Input
                id="abstract_char_limit"
                type="number"
                min="500"
                max="3000"
                value={defaults.abstract_char_limit}
                onChange={(e) =>
                  setDefaults({
                    ...defaults,
                    abstract_char_limit: parseInt(e.target.value) || 1500,
                  })
                }
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Visual Limits */}
        <div>
          <h3 className="text-lg font-semibold mb-4">Visual Elements</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="max_tables">Max Tables</Label>
              <Input
                id="max_tables"
                type="number"
                min="0"
                max="50"
                value={defaults.max_tables}
                onChange={(e) =>
                  setDefaults({
                    ...defaults,
                    max_tables: parseInt(e.target.value) || 10,
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="max_figures">Max Figures</Label>
              <Input
                id="max_figures"
                type="number"
                min="0"
                max="50"
                value={defaults.max_figures}
                onChange={(e) =>
                  setDefaults({
                    ...defaults,
                    max_figures: parseInt(e.target.value) || 10,
                  })
                }
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Citation Style */}
        <div>
          <h3 className="text-lg font-semibold mb-4">Citation Style</h3>
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="numeric_superscript"
                checked={defaults.citation_style.numeric_superscript}
                onCheckedChange={(checked) =>
                  setDefaults({
                    ...defaults,
                    citation_style: {
                      ...defaults.citation_style,
                      numeric_superscript: checked === true,
                    },
                  })
                }
              />
              <Label htmlFor="numeric_superscript" className="cursor-pointer">
                Use numeric superscripts (e.g., [1], [2])
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="order_of_appearance"
                checked={defaults.citation_style.order_of_appearance}
                onCheckedChange={(checked) =>
                  setDefaults({
                    ...defaults,
                    citation_style: {
                      ...defaults.citation_style,
                      order_of_appearance: checked === true,
                    },
                  })
                }
              />
              <Label htmlFor="order_of_appearance" className="cursor-pointer">
                Number citations by order of appearance
              </Label>
            </div>
          </div>
        </div>

        <Separator />

        {/* Locking Defaults */}
        <div>
          <h3 className="text-lg font-semibold mb-4">Locking Defaults</h3>
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="locked_sections_immutable"
                checked={defaults.locking_defaults.locked_sections_immutable}
                onCheckedChange={(checked) =>
                  setDefaults({
                    ...defaults,
                    locking_defaults: {
                      ...defaults.locking_defaults,
                      locked_sections_immutable: checked === true,
                    },
                  })
                }
              />
              <Label htmlFor="locked_sections_immutable" className="cursor-pointer">
                Locked sections cannot be modified by synthesis
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="allow_citation_reindexing"
                checked={defaults.locking_defaults.allow_citation_reindexing_without_text_change}
                onCheckedChange={(checked) =>
                  setDefaults({
                    ...defaults,
                    locking_defaults: {
                      ...defaults.locking_defaults,
                      allow_citation_reindexing_without_text_change: checked === true,
                    },
                  })
                }
              />
              <Label htmlFor="allow_citation_reindexing" className="cursor-pointer">
                Allow citation renumbering without text modification
              </Label>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-4">
          <Button onClick={handleSave} disabled={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            {isSaving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
