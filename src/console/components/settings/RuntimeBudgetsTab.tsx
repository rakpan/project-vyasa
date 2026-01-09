"use client"

import { useEffect, useState } from "react"
import { Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { toast } from "@/hooks/use-toast"

interface RuntimeBudgets {
  tier_a: {
    retrieval_top_k: number
    rerank_top_m: number
    candidate_trunc_tokens: number
    snippet_min_tokens: number
    snippet_max_tokens: number
    max_snippets: number
  }
  tier_b: {
    shared_prefix_max_tokens: number
    packet_a_max_tokens: number
    packet_b_max_tokens: number
    output_max_tokens_by_agent: {
      synthesizer: number
      critic: number
      cartographer_pass2: number
    }
    critic_bounded_retry_max: number
  }
}

export function RuntimeBudgetsTab() {
  const [budgets, setBudgets] = useState<RuntimeBudgets | null>(null)
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
        setBudgets(data.runtime_budgets || null)
      } else {
        toast({
          title: "Failed to load settings",
          description: "Could not load runtime budgets. Using defaults.",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error("Failed to load settings:", error)
      toast({
        title: "Error",
        description: "Failed to load runtime budget settings.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    if (!budgets) return

    try {
      setIsSaving(true)
      const response = await fetch("/api/proxy/orchestrator/api/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          runtime_budgets: budgets,
        }),
      })

      if (response.ok) {
        toast({
          title: "Saved",
          description: "Runtime budget settings saved successfully.",
        })
      } else {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || "Failed to save settings")
      }
    } catch (error) {
      console.error("Failed to save settings:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to save runtime budget settings.",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading || !budgets) {
    return <div className="text-center py-8 text-muted-foreground">Loading...</div>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Runtime Budgets</CardTitle>
        <CardDescription>
          Configure token limits and resource budgets for Tier A (CPU/Embedder) and Tier B (GPU/Nemotron-49B) operations.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Tier A Budgets */}
        <div>
          <h3 className="text-lg font-semibold mb-4">Tier A (CPU/Embedder-bound)</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="retrieval_top_k">Retrieval Top-K</Label>
              <Input
                id="retrieval_top_k"
                type="number"
                min="1"
                max="256"
                value={budgets.tier_a.retrieval_top_k}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_a: { ...budgets.tier_a, retrieval_top_k: parseInt(e.target.value) || 64 },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="rerank_top_m">Rerank Top-M</Label>
              <Input
                id="rerank_top_m"
                type="number"
                min="1"
                max="64"
                value={budgets.tier_a.rerank_top_m}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_a: { ...budgets.tier_a, rerank_top_m: parseInt(e.target.value) || 24 },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="candidate_trunc_tokens">Candidate Truncate Tokens</Label>
              <Input
                id="candidate_trunc_tokens"
                type="number"
                min="100"
                max="2000"
                value={budgets.tier_a.candidate_trunc_tokens}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_a: { ...budgets.tier_a, candidate_trunc_tokens: parseInt(e.target.value) || 600 },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="snippet_min_tokens">Snippet Min Tokens</Label>
              <Input
                id="snippet_min_tokens"
                type="number"
                min="10"
                max="500"
                value={budgets.tier_a.snippet_min_tokens}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_a: { ...budgets.tier_a, snippet_min_tokens: parseInt(e.target.value) || 50 },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="snippet_max_tokens">Snippet Max Tokens</Label>
              <Input
                id="snippet_max_tokens"
                type="number"
                min="100"
                max="2000"
                value={budgets.tier_a.snippet_max_tokens}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_a: { ...budgets.tier_a, snippet_max_tokens: parseInt(e.target.value) || 800 },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="max_snippets">Max Snippets</Label>
              <Input
                id="max_snippets"
                type="number"
                min="5"
                max="50"
                value={budgets.tier_a.max_snippets}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_a: { ...budgets.tier_a, max_snippets: parseInt(e.target.value) || 20 },
                  })
                }
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Tier B Budgets */}
        <div>
          <h3 className="text-lg font-semibold mb-4">Tier B (GPU/Nemotron-49B-bound)</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="shared_prefix_max_tokens">Shared Prefix Max Tokens</Label>
              <Input
                id="shared_prefix_max_tokens"
                type="number"
                min="0"
                max="16384"
                value={budgets.tier_b.shared_prefix_max_tokens}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_b: { ...budgets.tier_b, shared_prefix_max_tokens: parseInt(e.target.value) || 4096 },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="packet_a_max_tokens">Packet A Max Tokens</Label>
              <Input
                id="packet_a_max_tokens"
                type="number"
                min="1000"
                max="32768"
                value={budgets.tier_b.packet_a_max_tokens}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_b: { ...budgets.tier_b, packet_a_max_tokens: parseInt(e.target.value) || 8192 },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="packet_b_max_tokens">Packet B Max Tokens</Label>
              <Input
                id="packet_b_max_tokens"
                type="number"
                min="500"
                max="8192"
                value={budgets.tier_b.packet_b_max_tokens}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_b: { ...budgets.tier_b, packet_b_max_tokens: parseInt(e.target.value) || 2048 },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="critic_bounded_retry_max">Critic Bounded Retry Max</Label>
              <Input
                id="critic_bounded_retry_max"
                type="number"
                min="0"
                max="3"
                value={budgets.tier_b.critic_bounded_retry_max}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_b: { ...budgets.tier_b, critic_bounded_retry_max: parseInt(e.target.value) || 1 },
                  })
                }
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Agent Output Tokens */}
        <div>
          <h3 className="text-lg font-semibold mb-4">Agent Output Max Tokens</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="output_synthesizer">Synthesizer</Label>
              <Input
                id="output_synthesizer"
                type="number"
                min="1"
                value={budgets.tier_b.output_max_tokens_by_agent.synthesizer}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_b: {
                      ...budgets.tier_b,
                      output_max_tokens_by_agent: {
                        ...budgets.tier_b.output_max_tokens_by_agent,
                        synthesizer: parseInt(e.target.value) || 4096,
                      },
                    },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="output_critic">Critic</Label>
              <Input
                id="output_critic"
                type="number"
                min="1"
                value={budgets.tier_b.output_max_tokens_by_agent.critic}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_b: {
                      ...budgets.tier_b,
                      output_max_tokens_by_agent: {
                        ...budgets.tier_b.output_max_tokens_by_agent,
                        critic: parseInt(e.target.value) || 2048,
                      },
                    },
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="output_cartographer">Cartographer Pass 2</Label>
              <Input
                id="output_cartographer"
                type="number"
                min="1"
                value={budgets.tier_b.output_max_tokens_by_agent.cartographer_pass2}
                onChange={(e) =>
                  setBudgets({
                    ...budgets,
                    tier_b: {
                      ...budgets.tier_b,
                      output_max_tokens_by_agent: {
                        ...budgets.tier_b.output_max_tokens_by_agent,
                        cartographer_pass2: parseInt(e.target.value) || 4096,
                      },
                    },
                  })
                }
              />
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
