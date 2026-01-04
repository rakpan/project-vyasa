/**
 * Search Results List Component
 * 
 * Displays search results with selection checkboxes and queue action.
 */

import { SearchResult } from "@/services/webSearchService";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { ExternalLink, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SearchResultsListProps {
  results: SearchResult[];
  selectedUrls: Set<string>;
  onToggleSelection: (url: string) => void;
  onQueueSelected: () => void;
  isQueueing?: boolean;
  disabled?: boolean;
}

export function SearchResultsList({
  results,
  selectedUrls,
  onToggleSelection,
  onQueueSelected,
  isQueueing = false,
  disabled = false,
}: SearchResultsListProps) {
  if (results.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No search results
      </div>
    );
  }
  
  const hasSelection = selectedUrls.size > 0;
  
  return (
    <div className="space-y-2">
      {/* Queue button (sticky at top) */}
      {hasSelection && (
        <div className="sticky top-0 z-10 bg-background border-b border-border pb-2 mb-2">
          <Button
            onClick={onQueueSelected}
            disabled={disabled || isQueueing}
            size="sm"
            className="w-full"
          >
            {isQueueing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Queueing...
              </>
            ) : (
              `Queue ${selectedUrls.size} URL${selectedUrls.size > 1 ? "s" : ""} for Review`
            )}
          </Button>
        </div>
      )}
      
      {/* Results list */}
      <div className="space-y-3">
        {results.map((result, index) => {
          const isSelected = selectedUrls.has(result.link);
          
          return (
            <div
              key={index}
              className={cn(
                "p-3 rounded-md border transition-colors",
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              )}
            >
              <div className="flex items-start gap-3">
                <Checkbox
                  checked={isSelected}
                  onCheckedChange={() => onToggleSelection(result.link)}
                  disabled={disabled || isQueueing}
                  className="mt-1"
                />
                
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-medium line-clamp-2">
                      {result.title}
                    </h4>
                    <a
                      href={result.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>
                  
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {result.snippet}
                  </p>
                  
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="truncate">{result.displayLink}</span>
                    {result.quality_tier && (
                      <span className={cn(
                        "px-1.5 py-0.5 rounded text-xs font-medium",
                        result.quality_tier === "high" && "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
                        result.quality_tier === "medium" && "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
                        result.quality_tier === "low" && "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                      )}>
                        {result.quality_tier}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

