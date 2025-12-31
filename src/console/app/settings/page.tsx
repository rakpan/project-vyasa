"use client"

/**
 * Project Settings Page - Configuration interface for project settings.
 * Includes Vocabulary Guard tab for managing forbidden words.
 */

import { useEffect, useState } from "react"
import { Plus, Trash2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { toast } from "@/hooks/use-toast"

interface ForbiddenWord {
  word: string
  alternative: string
}

export default function SettingsPage() {
  const [forbiddenWords, setForbiddenWords] = useState<ForbiddenWord[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [newWord, setNewWord] = useState("")
  const [newAlternative, setNewAlternative] = useState("")

  useEffect(() => {
    loadForbiddenWords()
  }, [])

  const loadForbiddenWords = async () => {
    try {
      setIsLoading(true)
      const response = await fetch("/api/settings/vocab-guard")
      if (response.ok) {
        const data = await response.json()
        setForbiddenWords(data.forbidden_words || [])
      } else {
        toast({
          title: "Failed to load vocabulary",
          description: "Could not load forbidden words. Using empty list.",
          variant: "destructive",
        })
        setForbiddenWords([])
      }
    } catch (error) {
      console.error("Failed to load forbidden words:", error)
      toast({
        title: "Error",
        description: "Failed to load vocabulary guard settings.",
        variant: "destructive",
      })
      setForbiddenWords([])
    } finally {
      setIsLoading(false)
    }
  }

  const handleAddWord = () => {
    const word = newWord.trim().toLowerCase()
    if (!word) {
      toast({
        title: "Invalid input",
        description: "Word cannot be empty.",
        variant: "destructive",
      })
      return
    }

    // Check for duplicates
    if (forbiddenWords.some((w) => w.word.toLowerCase() === word)) {
      toast({
        title: "Duplicate word",
        description: `"${word}" is already in the list.`,
        variant: "destructive",
      })
      return
    }

    setForbiddenWords([...forbiddenWords, { word, alternative: newAlternative.trim() }])
    setNewWord("")
    setNewAlternative("")
  }

  const handleRemoveWord = (word: string) => {
    setForbiddenWords(forbiddenWords.filter((w) => w.word !== word))
  }

  const handleSave = async () => {
    try {
      setIsSaving(true)
      const response = await fetch("/api/settings/vocab-guard", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          forbidden_words: forbiddenWords,
        }),
      })

      if (response.ok) {
        toast({
          title: "Saved",
          description: "Vocabulary guard settings saved successfully.",
        })
      } else {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || "Failed to save settings")
      }
    } catch (error) {
      console.error("Failed to save forbidden words:", error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to save vocabulary guard settings.",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">Project Settings</h1>

      <Tabs defaultValue="vocab-guard" className="w-full">
        <TabsList>
          <TabsTrigger value="vocab-guard">Vocabulary Guard</TabsTrigger>
        </TabsList>

        <TabsContent value="vocab-guard" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Forbidden Vocabulary</CardTitle>
              <CardDescription>
                Configure words that should not be used in attorney-style write-ups.
                The system will suggest alternatives and flag violations during synthesis.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Add new word form */}
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <label className="text-sm font-medium mb-1 block">Forbidden Word</label>
                    <Input
                      placeholder="e.g., crisis"
                      value={newWord}
                      onChange={(e) => setNewWord(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          handleAddWord()
                        }
                      }}
                    />
                  </div>
                  <div className="flex-1">
                    <label className="text-sm font-medium mb-1 block">Alternative (optional)</label>
                    <Input
                      placeholder="e.g., significant challenge"
                      value={newAlternative}
                      onChange={(e) => setNewAlternative(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          handleAddWord()
                        }
                      }}
                    />
                  </div>
                  <Button onClick={handleAddWord} type="button">
                    <Plus className="h-4 w-4 mr-2" />
                    Add
                  </Button>
                </div>

                {/* Words table */}
                {isLoading ? (
                  <div className="text-center py-8 text-muted-foreground">Loading...</div>
                ) : forbiddenWords.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No forbidden words configured. Add words above to get started.
                  </div>
                ) : (
                  <div className="border rounded-md">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[200px]">Word</TableHead>
                          <TableHead>Alternative</TableHead>
                          <TableHead className="w-[100px]">Action</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {forbiddenWords.map((item) => (
                          <TableRow key={item.word}>
                            <TableCell className="font-medium">{item.word}</TableCell>
                            <TableCell className="text-muted-foreground">
                              {item.alternative || <span className="italic">(no alternative specified)</span>}
                            </TableCell>
                            <TableCell>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleRemoveWord(item.word)}
                                type="button"
                              >
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}

                {/* Save button */}
                <div className="flex justify-end pt-4">
                  <Button onClick={handleSave} disabled={isSaving || isLoading}>
                    <Save className="h-4 w-4 mr-2" />
                    {isSaving ? "Saving..." : "Save Changes"}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

