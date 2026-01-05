/**
 * Proxy route for Orchestrator API calls from client-side.
 * 
 * Routes:
 *   /api/proxy/orchestrator/workflow/submit -> http://orchestrator:8000/workflow/submit
 *   /api/proxy/orchestrator/workflow/status/:id -> http://orchestrator:8000/workflow/status/:id
 */

import { NextRequest, NextResponse } from 'next/server';

// Orchestrator URL configuration
// Priority: 1. ORCHESTRATOR_URL env var, 2. NEXT_PUBLIC_ORCHESTRATOR_URL (for client-side), 3. Default
const ORCHESTRATOR_URL = 
  process.env.ORCHESTRATOR_URL || 
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || 
  'http://orchestrator:8000';

/**
 * Retry configuration for orchestrator requests
 */
const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY_MS = 500; // Start with 500ms
const MAX_RETRY_DELAY_MS = 5000; // Cap at 5 seconds

/**
 * Check if an error is retryable (temporary connection issue)
 */
function isRetryableError(error: unknown): boolean {
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    return (
      message.includes('econnrefused') ||
      message.includes('connection refused') ||
      message.includes('fetch failed') ||
      message.includes('network') ||
      message.includes('timeout') ||
      message.includes('econnreset')
    );
  }
  return false;
}

/**
 * Sleep for specified milliseconds
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Retry fetch with exponential backoff
 */
async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries: number = MAX_RETRIES,
  initialDelay: number = INITIAL_RETRY_DELAY_MS
): Promise<Response> {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);
      // If we get a response (even if error status), return it
      // Only retry on network/connection errors
      return response;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // Only retry on retryable errors
      if (!isRetryableError(error) || attempt === maxRetries) {
        throw lastError;
      }
      
      // Exponential backoff: delay = initialDelay * 2^attempt, capped at MAX_RETRY_DELAY_MS
      const delay = Math.min(initialDelay * Math.pow(2, attempt), MAX_RETRY_DELAY_MS);
      console.log(`[Proxy] Retry attempt ${attempt + 1}/${maxRetries} after ${delay}ms for ${url}`);
      await sleep(delay);
    }
  }
  
  throw lastError || new Error('Failed after retries');
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: pathArray } = await params;
  const path = pathArray.join('/');
  const url = new URL(request.url);
  const queryString = url.search;
  const isStream = path.includes('/stream');

  try {
    // Get session for authentication
    const { auth } = await import('@/auth');
    const session = await auth();
    
    const headers: HeadersInit = {
      'Content-Type': isStream ? 'text/event-stream' : 'application/json',
    };
    
    // Include Authorization header if session exists
    // Note: For JWT-based auth, we would extract the token from the session
    // For cookie-based auth (NextAuth default), the session is validated server-side
    
    const targetUrl = `${ORCHESTRATOR_URL}/${path}${queryString ? `?${queryString}` : ''}`;
    console.log(`[Proxy] GET ${targetUrl}`);
    
    const response = await fetchWithRetry(targetUrl, {
      method: 'GET',
      headers,
      // Add timeout to prevent hanging
      signal: AbortSignal.timeout(30000), // 30 second timeout
    });

    // Handle SSE streaming
    if (isStream && response.body) {
      return new NextResponse(response.body, {
        status: response.status,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',
        },
      });
    }

    // Handle error responses from orchestrator
    if (!response.ok) {
      let errorData: any;
      try {
        errorData = await response.json();
      } catch {
        // If response is not JSON, get text
        const errorText = await response.text();
        errorData = { error: errorText || `Orchestrator returned ${response.status}` };
      }
      console.error(`Orchestrator proxy GET error (${response.status}):`, errorData);
      return NextResponse.json(
        { error: errorData.error || 'Orchestrator request failed', details: errorData },
        { status: response.status }
      );
    }

    // Handle regular JSON responses
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    // Network errors, connection refused, etc.
    const errorMessage = error instanceof Error ? error.message : String(error);
    const isRetryable = isRetryableError(error);
    
    console.error('Orchestrator proxy GET error:', errorMessage);
    console.error('Full error:', error);
    
    // For retryable errors, indicate it's temporary and suggest retry
    if (isRetryable) {
      return NextResponse.json(
        { 
          error: 'Orchestrator service is temporarily unavailable',
          details: errorMessage,
          hint: 'The orchestrator may be starting up. The request will be retried automatically.',
          code: 'ORCHESTRATOR_UNAVAILABLE',
          retryable: true,
          retry_after: 2, // Suggest retry after 2 seconds
        },
        { 
          status: 503,
          headers: {
            'Retry-After': '2', // HTTP standard header for retry timing
          }
        }
      );
    }
    
    // For non-retryable errors, return standard error
    return NextResponse.json(
      { 
        error: 'Failed to proxy request to orchestrator',
        details: errorMessage,
        hint: 'Check if orchestrator service is running and ORCHESTRATOR_URL is correct',
        code: 'ORCHESTRATOR_ERROR',
        retryable: false,
      },
      { status: 503 }
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: pathArray } = await params;
  const path = pathArray.join('/');
  const contentType = request.headers.get('content-type') || '';

  try {
    // Get session for authentication
    const { auth } = await import('@/auth');
    const session = await auth();
    
    let body: BodyInit;
    let headers: HeadersInit = {};

    if (contentType.includes('multipart/form-data')) {
      // Forward FormData as-is
      body = await request.formData();
      // Don't set Content-Type - fetch will set it with boundary
    } else {
      // JSON request
      body = await request.text();
      headers['Content-Type'] = 'application/json';
    }
    
    // Include Authorization header if session exists
    // Note: For JWT-based auth, we would extract the token from the session
    // For cookie-based auth (NextAuth default), the session is validated server-side

    const targetUrl = `${ORCHESTRATOR_URL}/${path}`;
    console.log(`[Proxy] POST ${targetUrl}`);
    
    const response = await fetchWithRetry(targetUrl, {
      method: 'POST',
      headers,
      body,
      // Add timeout to prevent hanging
      signal: AbortSignal.timeout(30000), // 30 second timeout
    });

    // Handle error responses from orchestrator
    if (!response.ok) {
      let errorData: any;
      try {
        errorData = await response.json();
      } catch {
        // If response is not JSON, get text
        const errorText = await response.text();
        errorData = { error: errorText || `Orchestrator returned ${response.status}` };
      }
      console.error(`Orchestrator proxy POST error (${response.status}):`, errorData);
      return NextResponse.json(
        { error: errorData.error || 'Orchestrator request failed', details: errorData },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    // Network errors, connection refused, etc.
    const errorMessage = error instanceof Error ? error.message : String(error);
    const isRetryable = isRetryableError(error);
    
    console.error('Orchestrator proxy POST error:', errorMessage);
    console.error('Full error:', error);
    
    // For retryable errors, indicate it's temporary and suggest retry
    if (isRetryable) {
      return NextResponse.json(
        { 
          error: 'Orchestrator service is temporarily unavailable',
          details: errorMessage,
          hint: 'The orchestrator may be starting up. The request will be retried automatically.',
          code: 'ORCHESTRATOR_UNAVAILABLE',
          retryable: true,
          retry_after: 2, // Suggest retry after 2 seconds
        },
        { 
          status: 503,
          headers: {
            'Retry-After': '2', // HTTP standard header for retry timing
          }
        }
      );
    }
    
    // For non-retryable errors, return standard error
    return NextResponse.json(
      { 
        error: 'Failed to proxy request to orchestrator',
        details: errorMessage,
        hint: 'Check if orchestrator service is running and ORCHESTRATOR_URL is correct',
        code: 'ORCHESTRATOR_ERROR',
        retryable: false,
      },
      { status: 503 }
    );
  }
}
