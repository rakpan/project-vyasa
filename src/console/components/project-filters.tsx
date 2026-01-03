"use client"

/**
 * Project Filters Component
 * Provides search input and filter controls (tags, rigor, status, date range)
 */

import { useState, useEffect } from "react"
import { Search, X, Filter } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

export interface ProjectFilters {
  query: string
  tags: string[]
  rigor: "exploratory" | "conservative" | null
  status: "Idle" | "Processing" | "AttentionNeeded" | null
  from: string
  to: string
}

interface ProjectFiltersProps {
  filters: ProjectFilters
  onFiltersChange: (filters: ProjectFilters) => void
  availableTags?: string[] // Optional: tags from all projects
}

export function ProjectFiltersComponent({
  filters,
  onFiltersChange,
  availableTags = [],
}: ProjectFiltersProps) {
  const [isPopoverOpen, setIsPopoverOpen] = useState(false)
  const [tagInput, setTagInput] = useState("")

  const hasActiveFilters =
    filters.query ||
    filters.tags.length > 0 ||
    filters.rigor ||
    filters.status ||
    filters.from ||
    filters.to

  const handleReset = () => {
    onFiltersChange({
      query: "",
      tags: [],
      rigor: null,
      status: null,
      from: "",
      to: "",
    })
    setIsPopoverOpen(false)
  }

  const handleAddTag = () => {
    const trimmed = tagInput.trim()
    if (trimmed && !filters.tags.includes(trimmed)) {
      onFiltersChange({
        ...filters,
        tags: [...filters.tags, trimmed],
      })
      setTagInput("")
    }
  }

  const handleRemoveTag = (tag: string) => {
    onFiltersChange({
      ...filters,
      tags: filters.tags.filter((t) => t !== tag),
    })
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Search Input */}
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search projects by title or tags..."
          value={filters.query}
          onChange={(e) =>
            onFiltersChange({ ...filters, query: e.target.value })
          }
          className="pl-9"
        />
      </div>

      {/* Quick Filters */}
      <Select
        value={filters.rigor || ""}
        onValueChange={(value) =>
          onFiltersChange({
            ...filters,
            rigor: value ? (value as "exploratory" | "conservative") : null,
          })
        }
      >
        <SelectTrigger className="w-[140px]">
          <SelectValue placeholder="Rigor" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">All Rigor</SelectItem>
          <SelectItem value="exploratory">Exploratory</SelectItem>
          <SelectItem value="conservative">Conservative</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={filters.status || ""}
        onValueChange={(value) =>
          onFiltersChange({
            ...filters,
            status: value
              ? (value as "Idle" | "Processing" | "AttentionNeeded")
              : null,
          })
        }
      >
        <SelectTrigger className="w-[140px]">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">All Status</SelectItem>
          <SelectItem value="Idle">Idle</SelectItem>
          <SelectItem value="Processing">Processing</SelectItem>
          <SelectItem value="AttentionNeeded">Attention Needed</SelectItem>
        </SelectContent>
      </Select>

      {/* Advanced Filters Popover */}
      <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm">
            <Filter className="h-4 w-4 mr-2" />
            More Filters
            {hasActiveFilters && (
              <Badge variant="secondary" className="ml-2 h-5 w-5 rounded-full p-0 flex items-center justify-center text-[10px]">
                {[
                  filters.tags.length,
                  filters.from ? 1 : 0,
                  filters.to ? 1 : 0,
                ].reduce((a, b) => a + b, 0)}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80" align="end">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Tags</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="Add tag..."
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault()
                      handleAddTag()
                    }
                  }}
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={handleAddTag}
                  disabled={!tagInput.trim()}
                >
                  Add
                </Button>
              </div>
              {filters.tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {filters.tags.map((tag) => (
                    <Badge
                      key={tag}
                      variant="secondary"
                      className="cursor-pointer"
                      onClick={() => handleRemoveTag(tag)}
                    >
                      {tag}
                      <X className="h-3 w-3 ml-1" />
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Date Range</Label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs text-muted-foreground">From</Label>
                  <Input
                    type="date"
                    value={filters.from}
                    onChange={(e) =>
                      onFiltersChange({ ...filters, from: e.target.value })
                    }
                    className="text-sm"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">To</Label>
                  <Input
                    type="date"
                    value={filters.to}
                    onChange={(e) =>
                      onFiltersChange({ ...filters, to: e.target.value })
                    }
                    className="text-sm"
                  />
                </div>
              </div>
            </div>

            {hasActiveFilters && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleReset}
                className="w-full"
              >
                <X className="h-4 w-4 mr-2" />
                Reset Filters
              </Button>
            )}
          </div>
        </PopoverContent>
      </Popover>

      {/* Active Filter Badges */}
      {hasActiveFilters && (
        <div className="flex items-center gap-2 flex-wrap">
          {filters.query && (
            <Badge variant="secondary" className="gap-1">
              Search: {filters.query}
              <X
                className="h-3 w-3 cursor-pointer"
                onClick={() => onFiltersChange({ ...filters, query: "" })}
              />
            </Badge>
          )}
          {filters.rigor && (
            <Badge variant="secondary" className="gap-1">
              Rigor: {filters.rigor}
              <X
                className="h-3 w-3 cursor-pointer"
                onClick={() => onFiltersChange({ ...filters, rigor: null })}
              />
            </Badge>
          )}
          {filters.status && (
            <Badge variant="secondary" className="gap-1">
              Status: {filters.status}
              <X
                className="h-3 w-3 cursor-pointer"
                onClick={() => onFiltersChange({ ...filters, status: null })}
              />
            </Badge>
          )}
        </div>
      )}
    </div>
  )
}

