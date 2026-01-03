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

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/');
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
    
    const response = await fetch(targetUrl, {
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
    console.error('Orchestrator proxy GET error:', errorMessage);
    console.error('Full error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to proxy request to orchestrator',
        details: errorMessage,
        hint: 'Check if orchestrator service is running and ORCHESTRATOR_URL is correct',
        code: 'ORCHESTRATOR_UNAVAILABLE',
      },
      { status: 503 }
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/');
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
    
    const response = await fetch(targetUrl, {
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
    console.error('Orchestrator proxy POST error:', errorMessage);
    console.error('Full error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to proxy request to orchestrator',
        details: errorMessage,
        hint: 'Check if orchestrator service is running and ORCHESTRATOR_URL is correct',
        code: 'ORCHESTRATOR_UNAVAILABLE',
      },
      { status: 503 }
    );
  }
}
