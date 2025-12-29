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
import { NextRequest, NextResponse } from 'next/server';
import { GraphDBType } from '@/lib/graph-db-service';

// In-memory storage for settings
let serverSettings: Record<string, string> = {};

/**
 * API Route to sync client settings with server environment variables
 * This allows us to use localStorage settings on the client side
 * and still access them as environment variables on the server side
 */
export async function POST(request: NextRequest) {
  try {
    const { settings } = await request.json();
    
    if (!settings || typeof settings !== 'object') {
      return NextResponse.json({ error: 'Settings object is required' }, { status: 400 });
    }
    
    // Update server settings
    serverSettings = { ...serverSettings, ...settings };
    
    // Log some important settings for debugging
    if (settings.graph_db_type) {
      console.log(`Setting graph database type to: ${settings.graph_db_type}`);
    }
    
    return NextResponse.json({
      success: true,
      message: 'Settings updated successfully'
    });
  } catch (error) {
    console.error('Error updating settings:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}

/**
 * GET /api/settings
 * Retrieve settings from the server side
 */
export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url);
    const key = url.searchParams.get('key');
    
    if (key) {
      // Return specific setting
      return NextResponse.json({
        [key]: serverSettings[key] || null
      });
    }
    
    // Return all settings (may want to filter sensitive ones in production)
    return NextResponse.json({
      settings: serverSettings
    });
  } catch (error) {
    console.error('Error retrieving settings:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}

/**
 * Helper function to get a setting value
 * For use in other API routes
 */
export function getSetting(key: string): string | null {
  return serverSettings[key] || null;
}

/**
 * Get the currently selected graph database type
 */
export function getGraphDbType(): GraphDBType {
  return (serverSettings.graph_db_type as GraphDBType) || 'arangodb';
} 