/**
 * API service for Review Queue operations.
 * Handles all HTTP requests to the orchestrator's review task endpoints.
 */

import { apiFetch, ApiError } from '@/lib/api';
import type { ReviewTask, ReviewStatus } from '@/types/review';

// Base URL for orchestrator API
const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || 
  (typeof window === 'undefined' 
    ? process.env.ORCHESTRATOR_URL || 'http://orchestrator:8000'
    : '/api/proxy/orchestrator');

const API_BASE = `${ORCHESTRATOR_URL}/api/review-tasks`;

/**
 * Extract a readable error message from various error types.
 */
function safeParseError(error: unknown): string {
  if (error instanceof ApiError) {
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
  return 'An unknown error occurred';
}

/**
 * List ReviewTasks for a project.
 * 
 * @param projectId - Project ID
 * @param status - Optional status filter
 * @param limit - Maximum number of tasks to return (default: 50)
 * @returns Promise resolving to array of ReviewTask
 * @throws ApiError if request fails
 */
export async function listReviewTasks(
  projectId: string,
  status?: ReviewStatus,
  limit: number = 50
): Promise<ReviewTask[]> {
  try {
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    if (status) {
      params.set('status', status);
    }
    params.set('limit', limit.toString());
    
    const response = await apiFetch<{ tasks: ReviewTask[] }>(`${API_BASE}?${params.toString()}`, {
      method: 'GET',
    });
    
    return response.tasks || [];
  } catch (error) {
    const message = safeParseError(error);
    throw new ApiError(message, error instanceof ApiError ? error.status : 500, error);
  }
}

/**
 * Get a single ReviewTask by ID.
 * 
 * @param reviewId - Review task ID
 * @returns Promise resolving to ReviewTask
 * @throws ApiError if request fails (404 if not found)
 */
export async function getReviewTask(reviewId: string): Promise<ReviewTask> {
  try {
    return await apiFetch<ReviewTask>(`${API_BASE}/${reviewId}`, {
      method: 'GET',
    });
  } catch (error) {
    const message = safeParseError(error);
    throw new ApiError(message, error instanceof ApiError ? error.status : 500, error);
  }
}

