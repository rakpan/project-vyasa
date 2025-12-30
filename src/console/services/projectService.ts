/**
 * API service for Project Kernel operations.
 * Handles all HTTP requests to the orchestrator's project endpoints.
 */

import { apiFetch, ApiError } from '@/lib/api';
import type { ProjectCreate, ProjectConfig, ProjectSummary } from '@/types/project';

// Base URL for orchestrator API
const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || 
  (typeof window === 'undefined' 
    ? process.env.ORCHESTRATOR_URL || 'http://orchestrator:8000'
    : '/api/proxy/orchestrator');

const API_BASE = `${ORCHESTRATOR_URL}/api/projects`;

/**
 * Extract a readable error message from various error types.
 */
export function safeParseError(error: unknown): string {
  if (error instanceof ApiError) {
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
    if ('error' in obj && typeof obj.error === 'string') {
      return obj.error;
    }
    if ('message' in obj && typeof obj.message === 'string') {
      return obj.message;
    }
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
    const message = safeParseError(error);
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

