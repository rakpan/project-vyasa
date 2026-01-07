/**
 * React hook for web search functionality in the workbench.
 * 
 * Provides search state management and API integration.
 */

import React, { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { searchWeb, queueUrls, SearchResult, QueueResponse } from "@/services/webSearchService";
import { toast } from "@/hooks/use-toast";
import { ToastAction } from "@/components/ui/toast";

export interface UseWebSearchOptions {
  projectId?: string;
  onQueueComplete?: (response: QueueResponse) => void;
}

export interface UseWebSearchReturn {
  // Search state
  query: string;
  setQuery: (query: string) => void;
  results: SearchResult[];
  isLoading: boolean;
  error: string | null;
  totalResults: number;
  
  // Search actions
  performSearch: () => Promise<void>;
  clearSearch: () => void;
  
  // Queue state
  selectedUrls: Set<string>;
  toggleUrlSelection: (url: string) => void;
  clearSelection: () => void;
  isQueueing: boolean;
  queueError: string | null;
  
  // Queue actions
  queueSelectedUrls: () => Promise<void>;
}

export function useWebSearch(options: UseWebSearchOptions = {}): UseWebSearchReturn {
  const { projectId, onQueueComplete } = options;
  const router = useRouter();
  
  // Search state
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalResults, setTotalResults] = useState(0);
  
  // Queue state
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [isQueueing, setIsQueueing] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  
  // Search actions
  const performSearch = useCallback(async () => {
    if (!query.trim()) {
      setError("Please enter a search query");
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await searchWeb(query, projectId);
      setResults(response.results);
      setTotalResults(response.total_results);
    } catch (err: any) {
      const errorMessage = err.message || "Search failed";
      setError(errorMessage);
      toast({
        title: "Search failed",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [query, projectId]);
  
  const clearSearch = useCallback(() => {
    setQuery("");
    setResults([]);
    setError(null);
    setTotalResults(0);
    setSelectedUrls(new Set());
  }, []);
  
  // Queue actions
  const toggleUrlSelection = useCallback((url: string) => {
    setSelectedUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) {
        next.delete(url);
      } else {
        next.add(url);
      }
      return next;
    });
  }, []);
  
  const clearSelection = useCallback(() => {
    setSelectedUrls(new Set());
  }, []);
  
  const queueSelectedUrls = useCallback(async () => {
    if (!projectId) {
      setQueueError("Project ID is required");
      toast({
        title: "Queue failed",
        description: "Project ID is required",
        variant: "destructive",
      });
      return;
    }
    
    if (selectedUrls.size === 0) {
      setQueueError("No URLs selected");
      toast({
        title: "Queue failed",
        description: "Please select at least one URL",
        variant: "destructive",
      });
      return;
    }
    
    setIsQueueing(true);
    setQueueError(null);
    
    try {
      const urls = Array.from(selectedUrls);
      const response = await queueUrls(urls, projectId, query);
      
      // Show status-specific toast with deep link to Review Queue
      if (response.status === "PENDING") {
        toast({
          title: "URLs queued for review",
          description: response.message || `Queued ${response.urls_queued} URL(s)`,
          action: (
            <ToastAction
              onClick={() => router.push(`/projects/${projectId}/review-queue`)}
            >
              View Queue
            </ToastAction>
          ),
        });
      } else {
        toast({
          title: "Queue failed",
          description: response.message || response.reason || "Failed to queue URLs",
          variant: "destructive",
        });
      }
      
      if (onQueueComplete) {
        onQueueComplete(response);
      }
      
      // Clear selection after queue attempt (success or failure)
      setSelectedUrls(new Set());
    } catch (err: any) {
      const errorMessage = err.message || "Queue failed";
      setQueueError(errorMessage);
      toast({
        title: "Queue failed",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsQueueing(false);
    }
  }, [selectedUrls, projectId, query, onQueueComplete]);
  
  return {
    // Search state
    query,
    setQuery,
    results,
    isLoading,
    error,
    totalResults,
    
    // Search actions
    performSearch,
    clearSearch,
    
    // Queue state
    selectedUrls,
    toggleUrlSelection,
    clearSelection,
    isQueueing,
    queueError,
    
    // Queue actions
    queueSelectedUrls,
  };
}

