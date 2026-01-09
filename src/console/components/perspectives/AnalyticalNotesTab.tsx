"use client"

/**
 * Analytical Notes Tab
 * 
 * Left: Filtered list of notes (filters: state, tags, linked RQ, search)
 * Right: Editor for creating/editing notes (text area, tags, link-to-RQ, save)
 */

import { useState, useEffect, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { toast } from "@/hooks/use-toast"
import { Loader2, Plus, Save, X, Search } from "lucide-react"
import { cn } from "@/lib/utils"
import { useProjectStore } from "@/state/useProjectStore"

interface AnalyticalNote {
  note_id: string
  project_id: string
  text: string
  tags: string[]
  state: "Draft" | "Manuscript"
  linked_rq: string | null
  created_at: string
  updated_at: string
}

interface AnalyticalNotesTabProps {
  projectId: string
}

export function AnalyticalNotesTab({ projectId }: AnalyticalNotesTabProps) {
  const [notes, setNotes] = useState<AnalyticalNote[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // Filters
  const [stateFilter, setStateFilter] = useState<string>("all")
  const [tagFilter, setTagFilter] = useState<string>("")
  const [rqFilter, setRqFilter] = useState<string>("")
  const [searchQuery, setSearchQuery] = useState<string>("")

  // Editor state
  const [editorText, setEditorText] = useState("")
  const [editorTags, setEditorTags] = useState<string[]>([])
  const [editorLinkedRq, setEditorLinkedRq] = useState<string>("")
  const [newTagInput, setNewTagInput] = useState("")

  // Get project RQs for linked RQ selector
  const { activeProject } = useProjectStore()
  const researchQuestions = activeProject?.research_questions || []
  const rqOptions = useMemo(() => {
    return researchQuestions.map((rq, idx) => ({
      id: `RQ${idx + 1}`,
      text: rq,
    }))
  }, [researchQuestions])

  // Fetch notes
  useEffect(() => {
    const fetchNotes = async () => {
      setIsLoading(true)
      try {
        const response = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/notes`)
        if (!response.ok) {
          throw new Error(`Failed to fetch notes: ${response.status}`)
        }
        const data = await response.json()
        // API returns direct array: [note1, note2, ...]
        setNotes(Array.isArray(data) ? data : [])
      } catch (error) {
        console.error("Failed to fetch notes:", error)
        toast({
          title: "Error",
          description: "Failed to load analytical notes",
          variant: "destructive",
        })
      } finally {
        setIsLoading(false)
      }
    }

    if (projectId) {
      fetchNotes()
    }
  }, [projectId])

  // Load selected note into editor
  useEffect(() => {
    if (selectedNoteId) {
      const note = notes.find((n) => n.note_id === selectedNoteId)
      if (note) {
        setEditorText(note.text)
        setEditorTags(note.tags || [])
        setEditorLinkedRq(note.linked_rq || "")
      }
    } else {
      // New note
      setEditorText("")
      setEditorTags([])
      setEditorLinkedRq("")
    }
  }, [selectedNoteId, notes])

  // Filter notes
  const filteredNotes = useMemo(() => {
    return notes.filter((note) => {
      if (stateFilter !== "all" && note.state !== stateFilter) return false
      if (tagFilter && !note.tags?.includes(tagFilter)) return false
      if (rqFilter && note.linked_rq !== rqFilter) return false
      if (searchQuery && !note.text.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    })
  }, [notes, stateFilter, tagFilter, rqFilter, searchQuery])

  // Get unique tags and RQs for filters
  const availableTags = useMemo(() => {
    const tags = new Set<string>()
    notes.forEach((note) => note.tags?.forEach((tag) => tags.add(tag)))
    return Array.from(tags).sort()
  }, [notes])

  const availableRqs = useMemo(() => {
    const rqs = new Set<string>()
    notes.forEach((note) => {
      if (note.linked_rq) rqs.add(note.linked_rq)
    })
    return Array.from(rqs).sort()
  }, [notes])

  // Save note
  const handleSave = async () => {
    if (!editorText.trim()) {
      toast({
        title: "Error",
        description: "Note text is required",
        variant: "destructive",
      })
      return
    }

    setIsSaving(true)
    try {
      if (selectedNoteId) {
        // Update existing note
        const response = await fetch(`/api/proxy/orchestrator/api/notes/${selectedNoteId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: editorText,
            tags: editorTags,
            linked_rq: editorLinkedRq || null,
          }),
        })

        if (!response.ok) {
          throw new Error(`Failed to update note: ${response.status}`)
        }

        toast({
          title: "Success",
          description: "Note updated successfully",
        })
      } else {
        // Create new note
        const response = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/notes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: editorText,
            tags: editorTags,
            linked_rq: editorLinkedRq || null,
          }),
        })

        if (!response.ok) {
          throw new Error(`Failed to create note: ${response.status}`)
        }

        const newNote = await response.json()
        toast({
          title: "Success",
          description: "Note created successfully",
        })

        setSelectedNoteId(newNote.note_id)
      }

      // Refresh notes list
      const refreshResponse = await fetch(`/api/proxy/orchestrator/api/projects/${projectId}/notes`)
      if (refreshResponse.ok) {
        const data = await refreshResponse.json()
        // API returns direct array: [note1, note2, ...]
        setNotes(Array.isArray(data) ? data : [])
      }
    } catch (error) {
      console.error("Failed to save note:", error)
      toast({
        title: "Error",
        description: "Failed to save note",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  // Add tag
  const handleAddTag = () => {
    if (newTagInput.trim() && !editorTags.includes(newTagInput.trim())) {
      setEditorTags([...editorTags, newTagInput.trim()])
      setNewTagInput("")
    }
  }

  // Remove tag
  const handleRemoveTag = (tag: string) => {
    setEditorTags(editorTags.filter((t) => t !== tag))
  }

  const selectedNote = notes.find((n) => n.note_id === selectedNoteId)

  return (
    <div className="flex-1 flex gap-4 min-h-0">
      {/* Left: Notes List */}
      <div className="w-1/3 flex flex-col border rounded-lg">
        <div className="p-4 border-b space-y-3">
          <div>
            <Label className="text-xs font-semibold">Filters</Label>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>

          {/* State filter */}
          <Select value={stateFilter} onValueChange={setStateFilter}>
            <SelectTrigger className="h-8 text-xs">
              <SelectValue placeholder="State" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All States</SelectItem>
              <SelectItem value="Draft">Draft</SelectItem>
              <SelectItem value="Manuscript">Manuscript</SelectItem>
            </SelectContent>
          </Select>

          {/* Tag filter */}
          {availableTags.length > 0 && (
            <Select value={tagFilter} onValueChange={setTagFilter}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Tag" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Tags</SelectItem>
                {availableTags.map((tag) => (
                  <SelectItem key={tag} value={tag}>
                    {tag}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {/* RQ filter */}
          {availableRqs.length > 0 && (
            <Select value={rqFilter} onValueChange={setRqFilter}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Linked RQ" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All RQs</SelectItem>
                {availableRqs.map((rq) => (
                  <SelectItem key={rq} value={rq}>
                    {rq}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Notes List */}
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-2">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            ) : filteredNotes.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                No notes found
              </div>
            ) : (
              filteredNotes.map((note) => (
                <Card
                  key={note.note_id}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-accent",
                    selectedNoteId === note.note_id && "bg-accent border-primary"
                  )}
                  onClick={() => setSelectedNoteId(note.note_id)}
                >
                  <CardContent className="p-3">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <Badge variant={note.state === "Manuscript" ? "default" : "secondary"} className="text-xs">
                        {note.state}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {new Date(note.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                    <p className="text-xs line-clamp-3 text-foreground">{note.text}</p>
                    {note.tags && note.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {note.tags.map((tag) => (
                          <Badge key={tag} variant="outline" className="text-[10px] px-1.5 py-0">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {note.linked_rq && (
                      <div className="mt-1 text-[10px] text-muted-foreground">
                        RQ: {note.linked_rq}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </ScrollArea>

        {/* New Note Button */}
        <div className="p-2 border-t">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => setSelectedNoteId(null)}
          >
            <Plus className="h-3 w-3 mr-1" />
            New Note
          </Button>
        </div>
      </div>

      {/* Right: Editor */}
      <div className="flex-1 flex flex-col border rounded-lg">
        <CardHeader className="border-b">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">
              {selectedNoteId ? "Edit Note" : "New Note"}
            </CardTitle>
            {selectedNote && (
              <Badge variant={selectedNote.state === "Manuscript" ? "default" : "secondary"}>
                {selectedNote.state}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Influence only, not citeable
          </p>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col p-4 space-y-4 min-h-0">
          {/* Text Editor */}
          <div className="flex-1 flex flex-col min-h-0">
            <Label htmlFor="note-text" className="text-xs font-semibold mb-2">
              Note Text
            </Label>
            <Textarea
              id="note-text"
              value={editorText}
              onChange={(e) => setEditorText(e.target.value)}
              placeholder="Enter your analytical note..."
              className="flex-1 min-h-[200px] text-sm"
            />
          </div>

          <Separator />

          {/* Tags */}
          <div>
            <Label className="text-xs font-semibold mb-2">Tags</Label>
            <div className="flex gap-2 mb-2">
              <Input
                placeholder="Add tag..."
                value={newTagInput}
                onChange={(e) => setNewTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    handleAddTag()
                  }
                }}
                className="h-8 text-xs"
              />
              <Button type="button" size="sm" onClick={handleAddTag} className="h-8">
                Add
              </Button>
            </div>
            {editorTags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {editorTags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    {tag}
                    <button
                      onClick={() => handleRemoveTag(tag)}
                      className="ml-1 hover:text-destructive"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Linked RQ */}
          <div>
            <Label htmlFor="linked-rq" className="text-xs font-semibold mb-2">
              Link to Research Question
            </Label>
            <Select value={editorLinkedRq} onValueChange={setEditorLinkedRq}>
              <SelectTrigger id="linked-rq" className="h-8 text-xs">
                <SelectValue placeholder="Select RQ (optional)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">None</SelectItem>
                {rqOptions.map((rq) => (
                  <SelectItem key={rq.id} value={rq.id}>
                    {rq.id}: {rq.text}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Save Button */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={isSaving || !editorText.trim()}>
              {isSaving ? (
                <>
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-3 w-3 mr-1" />
                  Save
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </div>
    </div>
  )
}

