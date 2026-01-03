/**
 * Observatory API proxy route
 * 
 * Proxies requests to the orchestrator's observatory endpoint.
 * The orchestrator exposes /api/system/observatory via FastAPI.
 */

import { NextRequest, NextResponse } from 'next/server';

const ORCHESTRATOR_URL = 
  process.env.ORCHESTRATOR_URL || 
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || 
  'http://orchestrator:8000';

export async function GET(request: NextRequest) {
  try {
    // Get session for authentication
    const { auth } = await import('@/auth');
    const session = await auth();
    
    if (!session) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const targetUrl = `${ORCHESTRATOR_URL}/api/system/observatory`;
    console.log(`[Observatory Proxy] GET ${targetUrl}`);
    
    const response = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
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
      console.error(`[Observatory Proxy] Error (${response.status}):`, errorData);
      return NextResponse.json(
        { error: errorData.error || 'Observatory request failed', details: errorData },
        { status: response.status }
      );
    }

    // Forward the response with headers (especially X-Vyasa-Snapshot-Age)
    const data = await response.json();
    const headers = new Headers();
    
    // Forward the snapshot age header if present
    const snapshotAge = response.headers.get('X-Vyasa-Snapshot-Age');
    if (snapshotAge) {
      headers.set('X-Vyasa-Snapshot-Age', snapshotAge);
    }
    
    return NextResponse.json(data, { 
      status: response.status,
      headers,
    });
  } catch (error) {
    // Network errors, connection refused, etc.
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('[Observatory Proxy] Error:', errorMessage);
    console.error('Full error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to proxy request to orchestrator',
        details: errorMessage,
        hint: 'Check if orchestrator service is running and ORCHESTRATOR_URL is correct'
      },
      { status: 500 }
    );
  }
}

