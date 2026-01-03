//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
import { NextRequest, NextResponse } from 'next/server';
import { QdrantService } from '@/lib/qdrant';

/**
 * Get Qdrant vector database stats
 * Replacement for deleted pinecone-diag/stats endpoint
 */
export async function GET() {
  try {
    const qdrantService = QdrantService.getInstance();
    const stats = await qdrantService.getStats();
    
    return NextResponse.json({
      ...stats,
      httpHealthy: stats.totalVectorCount >= 0, // Consider healthy if we got a response
      source: 'qdrant',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('Error getting Qdrant stats:', error);
    
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    return NextResponse.json(
      { 
        error: `Failed to get Qdrant stats: ${errorMessage}`,
        totalVectorCount: 0,
        httpHealthy: false,
        source: 'qdrant'
      },
      { status: 500 }
    );
  }
}

