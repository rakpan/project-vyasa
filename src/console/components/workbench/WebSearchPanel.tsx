/**
 * Web Search Panel Component for Project Vyasa Workbench.
 * 
 * Provides Google Custom Search integration and URL queueing
 * into the governance review flow.
 */

"use client";

import { useState } from "react";
import { useWebSearch } from "@/hooks/useWebSearch";
import { SearchResultsList } from "./SearchResultsList";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Search, X, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface WebSearchPanelProps {
  projectId: string;
  onQueueComplete?: (reviewTaskId: string) => void;
}

export function WebSearchPanel({
  projectId,
  onQueueComplete,
}: WebSearchPanelProps) {
  const {
    query,
    setQuery,
    results,
    isLoading,
    error,
    totalResults,
    performSearch,
    clearSearch,
    selectedUrls,
    toggleUrlSelection,
    clearSelection,
    isQueueing,
    queueSelectedUrls,
  } = useWebSearch({
    projectId,
    onQueueComplete: (response) => {
      if (onQueueComplete && response.review_task_id) {
        onQueueComplete(response.review_task_id);
      }
    },
  });
  
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    await performSearch();
  };
  
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSearch(e);
    }
  };
  
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-muted/30">
        <h2 className="text-sm font-semibold text-foreground">Web Search</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Search and queue URLs for review
        </p>
        <p className="text-xs text-muted-foreground mt-1 italic">
          Results restricted to approved domains
        </p>
      </div>
      
      {/* Search input */}
      <div className="p-4 border-b border-border">
        <form onSubmit={handleSearch} className="space-y-2">
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="Search the web..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading || isQueueing}
              className="flex-1"
            />
            <Button
              type="submit"
              disabled={isLoading || isQueueing || !query.trim()}
              size="default"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
            </Button>
            {results.length > 0 && (
              <Button
                type="button"
                variant="ghost"
                size="default"
                onClick={clearSearch}
                disabled={isLoading || isQueueing}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </form>
        
        {/* Results count and allowlist note */}
        {totalResults > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-xs text-muted-foreground">
              {results.length} of {totalResults.toLocaleString()} results
            </p>
            {results.length < totalResults && (
              <p className="text-xs text-muted-foreground italic">
                Showing only results from approved domains
              </p>
            )}
          </div>
        )}
      </div>
      
      {/* Error display */}
      {error && (
        <div className="p-4">
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}
      
      {/* Results */}
      <div className="flex-1 overflow-auto p-4">
        <SearchResultsList
          results={results}
          selectedUrls={selectedUrls}
          onToggleSelection={toggleUrlSelection}
          onQueueSelected={queueSelectedUrls}
          isQueueing={isQueueing}
          disabled={isLoading}
        />
      </div>
      
      {/* Footer info */}
      {results.length === 0 && !isLoading && !error && (
        <div className="p-4 border-t border-border">
          <p className="text-xs text-muted-foreground text-center">
            Enter a search query to find web sources
          </p>
        </div>
      )}
    </div>
  );
}

