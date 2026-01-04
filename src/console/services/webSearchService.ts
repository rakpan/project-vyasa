/**
 * Web Search Service for Project Vyasa Workbench.
 * 
 * Provides client-side API for Google Custom Search integration
 * and URL queueing into the governance review flow.
 */

export interface SearchResult {
  title: string;
  link: string;
  snippet: string;
  displayLink: string;
  quality_tier?: "high" | "medium" | "low";
  quality_score?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total_results: number;
  reason?: string;
  message?: string;
}

export interface QueueResponse {
  review_task_id: string;
  status: "PENDING" | "FAILED";
  urls_queued: number;
  urls_failed: number;
  message: string;
  reason?: string;
}

/**
 * Search the web using Google Custom Search JSON API.
 * 
 * @param query - Search query string
 * @param projectId - Optional project ID for context
 * @returns Search results
 */
export async function searchWeb(
  query: string,
  projectId?: string
): Promise<SearchResponse> {
  const response = await fetch("/api/proxy/orchestrator/api/web-search/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query: query.trim(),
      project_id: projectId,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(error.error || `Search failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Queue selected URLs into the governance review flow.
 * 
 * URLs will be scraped via Firecrawl, extracted via Worker,
 * and added to a ReviewTask with status PENDING.
 * 
 * @param urls - List of URLs to queue
 * @param projectId - Project ID (required)
 * @param query - Optional search query for context
 * @returns Queue response with review task ID
 */
export async function queueUrls(
  urls: string[],
  projectId: string,
  query?: string
): Promise<QueueResponse> {
  const response = await fetch("/api/proxy/orchestrator/api/web-search/queue", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      urls: urls,
      project_id: projectId,
      query: query,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(error.error || `Queue failed: ${response.status}`);
  }

  return response.json();
}

