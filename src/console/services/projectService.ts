/**
 * API service for Project Kernel operations.
 * Handles all HTTP requests to the orchestrator's project endpoints.
 */

import { apiFetch, ApiError } from '@/lib/api';
import type { ProjectCreate, ProjectConfig, ProjectSummary, ProjectGrouping } from '@/types/project';

// Base URL for orchestrator API
const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || 
  (typeof window === 'undefined' 
    ? process.env.ORCHESTRATOR_URL || 'http://orchestrator:8000'
    : '/api/proxy/orchestrator');

const API_BASE = `${ORCHESTRATOR_URL}/api/projects`;

/**
 * Extract a readable error message from various error types.
 * Includes details and hints from proxy error responses.
 */
export function safeParseError(error: unknown): string {
  if (error instanceof ApiError) {
    // Check if the error body contains details or hints
    const body = error.body as any;
    if (body && typeof body === 'object') {
      const parts: string[] = [error.message];
      if (body.details && typeof body.details === 'string') {
        parts.push(`Details: ${body.details}`);
      }
      if (body.hint && typeof body.hint === 'string') {
        parts.push(`Hint: ${body.hint}`);
      }
      return parts.join('\n');
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  if (typeof error === 'object' && error !== null) {
    const obj = error as Record<string, unknown>;
    const parts: string[] = [];
    
    if ('error' in obj && typeof obj.error === 'string') {
      parts.push(obj.error);
    } else if ('message' in obj && typeof obj.message === 'string') {
      parts.push(obj.message);
    }
    
    // Include details and hints if available
    if ('details' in obj && typeof obj.details === 'string') {
      parts.push(`Details: ${obj.details}`);
    }
    if ('hint' in obj && typeof obj.hint === 'string') {
      parts.push(`Hint: ${obj.hint}`);
    }
    
    return parts.length > 0 ? parts.join('\n') : 'An unknown error occurred';
  }
  return 'An unknown error occurred';
}

/**
 * Create a new project.
 * 
 * @param payload - ProjectCreate payload
 * @returns Promise resolving to ProjectConfig
 * @throws ApiError if request fails
 */
export async function createProject(payload: ProjectCreate): Promise<ProjectConfig> {
  try {
    return await apiFetch<ProjectConfig>(API_BASE, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    const message = safeParseError(error);
    throw new ApiError(message, error instanceof ApiError ? error.status : 500, error);
  }
}

/**
 * List all projects as summaries.
 * 
 * @returns Promise resolving to array of ProjectSummary
 * @throws ApiError if request fails
 */
export async function listProjects(): Promise<ProjectSummary[]> {
  try {
    return await apiFetch<ProjectSummary[]>(API_BASE, {
      method: 'GET',
    });
  } catch (error) {
    let message = safeParseError(error);
    const body = error instanceof ApiError ? error.body : null;
    const bodyAsObject = typeof body === 'object' && body !== null ? (body as any) : null;
    const combinedDetails = [
      message,
      typeof body === 'string' ? body : '',
      bodyAsObject?.error,
      bodyAsObject?.details,
      bodyAsObject?.hint,
    ]
      .filter((part) => typeof part === 'string')
      .join(' ')
      .toLowerCase();

    const orchestratorUnavailable =
      (
        error instanceof ApiError &&
        error.status >= 500 &&
        (
          bodyAsObject?.code === 'ORCHESTRATOR_UNAVAILABLE' ||
          combinedDetails.includes('fetch failed') ||
          combinedDetails.includes('connection refused') ||
          combinedDetails.includes('econnrefused') ||
          combinedDetails.includes('failed to proxy request') ||
          combinedDetails.includes('orchestrator service is not available')
        )
      ) ||
      (
        !(error instanceof ApiError) &&
        (combinedDetails.includes('fetch failed') || combinedDetails.includes('failed to fetch'))
      );

    if (orchestratorUnavailable) {
      console.warn('Orchestrator unavailable while listing projects; returning empty list.');
      return [];
    }
    
    // Provide user-friendly message for orchestrator connection errors
    if (error instanceof ApiError && error.status === 500) {
      if (bodyAsObject?.details && typeof bodyAsObject.details === 'string') {
        // Check if it's a connection error
        if (bodyAsObject.details.includes('ECONNREFUSED') || 
            bodyAsObject.details.includes('fetch failed') ||
            bodyAsObject.details.includes('Connection refused')) {
          message = `Orchestrator service is not available. Please ensure the orchestrator service is running.\n\n${message}`;
        }
      }
    }
    
    throw new ApiError(message, error instanceof ApiError ? error.status : 500, error);
  }
}

/**
 * Get a project by ID.
 * 
 * @param id - Project UUID
 * @returns Promise resolving to ProjectConfig
 * @throws ApiError if request fails (404 if not found)
 */
export async function getProject(id: string): Promise<ProjectConfig> {
  try {
    return await apiFetch<ProjectConfig>(`${API_BASE}/${id}`, {
      method: 'GET',
    });
  } catch (error) {
    const message = safeParseError(error);
    throw new ApiError(message, error instanceof ApiError ? error.status : 500, error);
  }
}

/**
 * Update project rigor level.
 */
export async function updateRigor(id: string, rigor: "exploratory" | "conservative"): Promise<ProjectConfig> {
  try {
    return await apiFetch<ProjectConfig>(`${API_BASE}/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rigor_level: rigor }),
    });
  } catch (error) {
    const message = safeParseError(error);
    throw new ApiError(message, error instanceof ApiError ? error.status : 500, error);
  }
}

/**
 * List projects with hub view (grouping, filtering, summaries).
 * 
 * @param filters - Filter parameters
 * @returns Promise resolving to ProjectGrouping
 * @throws ApiError if request fails
 */
export async function listProjectsHub(filters?: {
  query?: string;
  tags?: string[];
  rigor?: "exploratory" | "conservative";
  status?: "Idle" | "Processing" | "AttentionNeeded";
  from?: string; // ISO date
  to?: string; // ISO date
  include_manifest?: boolean;
}): Promise<ProjectGrouping> {
  try {
    const params = new URLSearchParams();
    params.set('view', 'hub');
    
    if (filters?.query) {
      params.set('query', filters.query);
    }
    if (filters?.tags && filters.tags.length > 0) {
      params.set('tags', filters.tags.join(','));
    }
    if (filters?.rigor) {
      params.set('rigor', filters.rigor);
    }
    if (filters?.status) {
      params.set('status', filters.status);
    }
    if (filters?.from) {
      params.set('from', filters.from);
    }
    if (filters?.to) {
      params.set('to', filters.to);
    }
    if (filters?.include_manifest) {
      params.set('include_manifest', 'true');
    }
    
    return await apiFetch<ProjectGrouping>(`${API_BASE}?${params.toString()}`, {
      method: 'GET',
    });
  } catch (error) {
    const message = safeParseError(error);
    throw new ApiError(message, error instanceof ApiError ? error.status : 500, error);
  }
}

/**
 * List all available project templates.
 * 
 * @returns Promise resolving to array of ProjectTemplate
 * @throws ApiError if request fails
 */
export async function listProjectTemplates(): Promise<ProjectTemplate[]> {
  try {
    return await apiFetch<ProjectTemplate[]>(`${API_BASE}/templates`, {
      method: 'GET',
    });
  } catch (error) {
    const message = safeParseError(error);
    // If endpoint fails, return empty array (frontend will use static fallback)
    if (error instanceof ApiError && error.status >= 500) {
      console.warn('Failed to fetch templates from server, using static fallback');
      return [];
    }
    throw new ApiError(message, error instanceof ApiError ? error.status : 500, error);
  }
}
