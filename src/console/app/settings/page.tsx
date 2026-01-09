"use client"

/**
 * Settings Page - Configuration interface for system settings.
 * 
 * Tabs:
 * 1. Runtime Budgets - Tier A/B limits and agent output tokens
 * 2. Prompt Profiles - Versioned prompt templates with validation
 * 3. Manuscript Defaults - Word limits, citation style, locking defaults
 * 4. Health & Dependencies - Read-only status display
 * 5. Vocabulary Guard - Forbidden words (existing)
 */

import { useEffect, useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { toast } from "@/hooks/use-toast"
import { RuntimeBudgetsTab } from "@/components/settings/RuntimeBudgetsTab"
import { PromptProfilesTab } from "@/components/settings/PromptProfilesTab"
import { ManuscriptDefaultsTab } from "@/components/settings/ManuscriptDefaultsTab"
import { HealthTab } from "@/components/settings/HealthTab"
import { VocabularyGuardTab } from "@/components/settings/VocabularyGuardTab"

export default function SettingsPage() {
  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <h1 className="text-3xl font-bold mb-6">System Settings</h1>

      <Tabs defaultValue="runtime-budgets" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="runtime-budgets">Runtime Budgets</TabsTrigger>
          <TabsTrigger value="prompt-profiles">Prompt Profiles</TabsTrigger>
          <TabsTrigger value="manuscript-defaults">Manuscript Defaults</TabsTrigger>
          <TabsTrigger value="health">Health & Dependencies</TabsTrigger>
          <TabsTrigger value="vocab-guard">Vocabulary Guard</TabsTrigger>
        </TabsList>

        <TabsContent value="runtime-budgets" className="mt-6">
          <RuntimeBudgetsTab />
        </TabsContent>

        <TabsContent value="prompt-profiles" className="mt-6">
          <PromptProfilesTab />
        </TabsContent>

        <TabsContent value="manuscript-defaults" className="mt-6">
          <ManuscriptDefaultsTab />
        </TabsContent>

        <TabsContent value="health" className="mt-6">
          <HealthTab />
        </TabsContent>

        <TabsContent value="vocab-guard" className="mt-6">
          <VocabularyGuardTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
