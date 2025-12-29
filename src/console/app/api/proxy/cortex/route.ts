//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
/**
 * Proxy API route for Cortex (SGLang) service
 * 
 * Forwards client-side requests to the Cortex service at CORTEX_SERVICE_URL.
 * This allows the frontend to make requests without CORS issues.
 */

import { NextRequest, NextResponse } from 'next/server';

const CORTEX_SERVICE_URL = process.env.CORTEX_SERVICE_URL || 'http://vyasa-cortex:30000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Forward the request to Cortex service's OpenAI-compatible endpoint
    const cortexUrl = `${CORTEX_SERVICE_URL}/v1/chat/completions`;
    
    console.log(`[Proxy] Forwarding request to Cortex: ${cortexUrl}`);
    
    const response = await fetch(cortexUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Cortex service error:', errorText);
      return NextResponse.json(
        { 
          error: 'Cortex service error', 
          details: errorText 
        },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('Error forwarding to Cortex service:', error);
    return NextResponse.json(
      { 
        error: 'Failed to connect to Cortex service',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

