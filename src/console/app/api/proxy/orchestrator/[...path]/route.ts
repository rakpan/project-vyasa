/**
 * Proxy route for Orchestrator API calls from client-side.
 * 
 * Routes:
 *   /api/proxy/orchestrator/workflow/submit -> http://orchestrator:8000/workflow/submit
 *   /api/proxy/orchestrator/workflow/status/:id -> http://orchestrator:8000/workflow/status/:id
 */

import { NextRequest, NextResponse } from 'next/server';

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || 'http://orchestrator:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/');
  const url = new URL(request.url);
  const queryString = url.search;

  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/${path}${queryString ? `?${queryString}` : ''}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Orchestrator proxy GET error:', error);
    return NextResponse.json(
      { error: 'Failed to proxy request to orchestrator' },
      { status: 500 }
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

    const response = await fetch(`${ORCHESTRATOR_URL}/${path}`, {
      method: 'POST',
      headers,
      body,
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('Orchestrator proxy POST error:', error);
    return NextResponse.json(
      { error: 'Failed to proxy request to orchestrator' },
      { status: 500 }
    );
  }
}

