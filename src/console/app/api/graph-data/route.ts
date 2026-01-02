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
import { type NextRequest, NextResponse } from "next/server"

// Utility function to generate UUID with fallback
const generateUUID = (): string => {
  // Check if crypto.randomUUID is available
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    try {
      return crypto.randomUUID();
    } catch (error) {
      console.warn('crypto.randomUUID failed, using fallback:', error);
    }
  }
  
  // Fallback UUID generation
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

// Create a more persistent storage mechanism (still in-memory but more reliable)
// This will be a global variable that persists between API calls
// In a production environment, you would use a database instead
const graphDataStore = new Map<string, { triples: any[]; documentName: string }>()

// Sample graph data for when no ID is provided
const sampleGraphData = {
  nodes: [
    { id: "1", name: "Document 1", group: "document" },
    { id: "2", name: "Machine Learning", group: "concept" },
    { id: "3", name: "Neural Networks", group: "concept" },
    { id: "4", name: "Deep Learning", group: "concept" },
    { id: "5", name: "Computer Vision", group: "concept" },
    { id: "6", name: "Natural Language Processing", group: "concept" },
    { id: "7", name: "Reinforcement Learning", group: "concept" },
    { id: "8", name: "Supervised Learning", group: "concept" },
    { id: "9", name: "Unsupervised Learning", group: "concept" },
    { id: "10", name: "Semi-supervised Learning", group: "concept" },
    { id: "11", name: "Transfer Learning", group: "concept" },
    { id: "12", name: "GPT-4", group: "important" },
    { id: "13", name: "BERT", group: "concept" },
    { id: "14", name: "Transformers", group: "concept" },
    { id: "15", name: "CNN", group: "concept" },
    { id: "16", name: "RNN", group: "concept" },
    { id: "17", name: "LSTM", group: "concept" },
    { id: "18", name: "GAN", group: "concept" },
    { id: "19", name: "Diffusion Models", group: "important" },
    { id: "20", name: "Document 2", group: "document" },
  ],
  links: [
    { source: "1", target: "2", name: "mentions" },
    { source: "1", target: "3", name: "discusses" },
    { source: "1", target: "4", name: "explains" },
    { source: "2", target: "3", name: "includes" },
    { source: "2", target: "4", name: "includes" },
    { source: "2", target: "5", name: "related_to" },
    { source: "2", target: "6", name: "related_to" },
    { source: "2", target: "7", name: "includes" },
    { source: "2", target: "8", name: "includes" },
    { source: "2", target: "9", name: "includes" },
    { source: "2", target: "10", name: "includes" },
    { source: "2", target: "11", name: "includes" },
    { source: "3", target: "15", name: "includes" },
    { source: "3", target: "16", name: "includes" },
    { source: "3", target: "17", name: "includes" },
    { source: "4", target: "12", name: "uses" },
    { source: "4", target: "13", name: "uses" },
    { source: "4", target: "14", name: "uses" },
    { source: "6", target: "12", name: "uses" },
    { source: "6", target: "13", name: "uses" },
    { source: "6", target: "14", name: "uses" },
    { source: "5", target: "15", name: "uses" },
    { source: "5", target: "18", name: "uses" },
    { source: "5", target: "19", name: "uses" },
    { source: "20", target: "6", name: "mentions" },
    { source: "20", target: "12", name: "discusses" },
    { source: "20", target: "19", name: "explains" },
  ]
};

export async function POST(request: NextRequest) {
  try {
    const { triples, documentName } = await request.json()

    if (!triples || !Array.isArray(triples)) {
      return NextResponse.json({ error: "Invalid triples data" }, { status: 400 })
    }

    // Generate a unique ID for this graph data
    const graphId = generateUUID()

    // Store the data
    graphDataStore.set(graphId, { triples, documentName: documentName || "Unnamed Document" })

    console.log(`Stored graph data with ID: ${graphId}, triples count: ${triples.length}`)

    // Return the ID
    return NextResponse.json({ graphId })
  } catch (error) {
    console.error("Error storing graph data:", error)
    return NextResponse.json({ error: "Failed to store graph data" }, { status: 500 })
  }
}

export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url)
    const graphId = url.searchParams.get("id")

    // If graphId is provided, check in-memory store first (for backward compatibility)
    if (graphId) {
      const graphData = graphDataStore.get(graphId)
      if (graphData) {
        console.log(`Found graph data in memory store with ${graphData.triples.length} triples`)
        return NextResponse.json(graphData)
      }
    }

    // Query ArangoDB (memory service) for graph data
    try {
      const memoryUrl = process.env.MEMORY_SERVICE_URL || 'http://graph:8529';
      const dbName = process.env.ARANGODB_DB || 'project_vyasa';
      const username = process.env.ARANGODB_USER || 'root';
      const password = process.env.ARANGODB_PASSWORD || '';

      // Create basic auth header using Node.js Buffer (NOT browser btoa())
      // Buffer.from().toString('base64') is the Node.js equivalent of btoa()
      const authHeader = Buffer.from(`${username}:${password}`).toString('base64');

      // Query entities using AQL
      const aqlUrl = `${memoryUrl}/_db/${dbName}/_api/cursor`;
      const aqlQuery = {
        query: `
          FOR entity IN entities
            LIMIT 1000
            RETURN entity
        `,
        batchSize: 1000,
      };

      const entitiesResponse = await fetch(aqlUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${authHeader}`,
        },
        body: JSON.stringify(aqlQuery),
      });

      // Query edges using AQL
      const edgesQuery = {
        query: `
          FOR edge IN edges
            LIMIT 1000
            RETURN edge
        `,
        batchSize: 1000,
      };

      const edgesResponse = await fetch(aqlUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Basic ${authHeader}`,
        },
        body: JSON.stringify(edgesQuery),
      });

      if (entitiesResponse.ok && edgesResponse.ok) {
        const entitiesData = await entitiesResponse.json();
        const edgesData = await edgesResponse.json();

        const entities = entitiesData.result || [];
        const edges = edgesData.result || [];

        // Transform to frontend format
        const nodes = entities.map((entity: any) => ({
          id: entity._id || entity._key,
          name: entity.name || entity._key,
          group: entity.type || 'entity',
          ...entity,
        }));

        const links = edges.map((edge: any) => ({
          source: edge._from?.split('/')[1] || edge._from,
          target: edge._to?.split('/')[1] || edge._to,
          name: edge.type || edge.predicate || 'related_to',
          ...edge,
        }));

        console.log(`Retrieved ${nodes.length} nodes and ${links.length} links from ArangoDB`);
        return NextResponse.json({ nodes, links });
      }
    } catch (dbError) {
      console.warn('Failed to query ArangoDB, falling back to sample data:', dbError);
    }

    // Fallback to sample data if no ID and DB query fails
    if (!graphId) {
      console.log("No graph ID provided and DB query failed, returning sample data")
      return NextResponse.json(sampleGraphData)
    }

    // If graphId provided but not found
    return NextResponse.json({ 
      redirect: true, 
      useLocalStorage: true,
      error: "Graph data not found or has expired"
    }, { status: 404 })
  } catch (error) {
    console.error("Error retrieving graph data:", error)
    return NextResponse.json({ error: "Failed to retrieve graph data" }, { status: 500 })
  }
}
