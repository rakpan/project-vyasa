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
import type { Triple } from '@/types/graph';
import { getGraphDbType } from '../settings/route';
import { getGraphDbService } from '@/lib/graph-db-util';
import { GraphDBType } from '@/lib/graph-db-service';

/**
 * API endpoint for processing documents with LangChain, generating embeddings,
 * and storing in the knowledge graph
 * POST /api/process-document
 */
export async function POST(req: NextRequest) {
  try {
    // Parse request body
    const body = await req.json();
    const { 
      text, 
      filename, 
      triples, 
      useLangChain, 
      useGraphTransformer,
      systemPrompt,
      extractionPrompt,
      graphTransformerPrompt
    } = body;

    // Validate required field: text is mandatory
    if (!text || typeof text !== 'string') {
      return NextResponse.json({ error: 'Text is required' }, { status: 400 });
    }

    console.log(`🔍 API: Processing document "${filename || 'unnamed'}" (${text.length} chars)`);
    
    // Triples are OPTIONAL - if missing, we will invoke orchestrator workflow
    let triplesForProcessing: Triple[] = [];
    
    if (!triples || !Array.isArray(triples) || triples.length === 0) {
      console.log('🔍 API: No triples provided - triggering orchestrator workflow (LangGraph)...');
      try {
        const orchestratorUrl = process.env.ORCHESTRATOR_URL || 'http://orchestrator:8000';
        
        // Use async job submission for long-running workflows
        const submitResponse = await fetch(`${orchestratorUrl}/workflow/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            raw_text: text,
            pdf_path: filename || 'api-request',
          }),
        });

        if (!submitResponse.ok) {
          const errorData = await submitResponse.json().catch(() => ({}));
          console.warn(`⚠️ API: Orchestrator job submission failed: ${errorData?.error || submitResponse.statusText}`);
        } else {
          const { job_id } = await submitResponse.json();
          console.log(`📋 API: Submitted orchestrator job ${job_id}, polling for completion...`);
          
          // Poll for completion (with timeout)
          const maxPollTime = 5 * 60 * 1000; // 5 minutes
          const pollInterval = 2000; // 2 seconds
          const startTime = Date.now();
          let completed = false;
          
          while (!completed && (Date.now() - startTime) < maxPollTime) {
            await new Promise(resolve => setTimeout(resolve, pollInterval));
            
            const statusResponse = await fetch(`${orchestratorUrl}/workflow/status/${job_id}`);
            if (!statusResponse.ok) {
              throw new Error(`Failed to get job status: ${statusResponse.statusText}`);
            }
            
            const status = await statusResponse.json();
            
            if (status.status === 'COMPLETED') {
              const extractedGraph = status.result?.extracted_json || {};
              const graphTriples = Array.isArray(extractedGraph?.triples) ? extractedGraph.triples : [];
              triplesForProcessing = graphTriples.map((triple: any) => ({
                subject: triple.subject,
                predicate: triple.predicate,
                object: triple.object,
                confidence: triple.confidence,
              })) as Triple[];
              console.log(`✅ API: Orchestrator job ${job_id} completed with ${triplesForProcessing.length} triples`);
              completed = true;
            } else if (status.status === 'FAILED') {
              throw new Error(status.error || 'Workflow job failed');
            }
            // Continue polling if PENDING or PROCESSING
          }
          
          if (!completed) {
            console.warn(`⚠️ API: Orchestrator job ${job_id} timed out after ${maxPollTime}ms`);
            // Return empty triples - user can retry
          }
        }
      } catch (workflowError) {
        console.error('❌ API: Orchestrator workflow error:', workflowError);
        // Fall through - triplesForProcessing remains empty
      }
    } else {
      // Manual Override Mode: Use provided triples
      console.log(`🔍 API: Using provided triples (${triples.length} total)...`);
      // Filter triples to ensure they are valid
      triplesForProcessing = triples.filter((triple: any) => {
        return (
          triple &&
          typeof triple.subject === 'string' && triple.subject.trim() !== '' &&
          typeof triple.predicate === 'string' && triple.predicate.trim() !== '' &&
          typeof triple.object === 'string' && triple.object.trim() !== ''
        );
      }) as Triple[];
      console.log(`✅ API: Validated ${triplesForProcessing.length} triples (filtered ${triples.length - triplesForProcessing.length} invalid)`);
    }

    // Generate documentId (use filename or generate UUID)
    const documentId = filename || `doc-${Date.now()}-${Math.random().toString(36).substring(7)}`;
    
    // Save triples to ArangoDB (or configured graph database)
    let graphData = { nodes: [], relationships: [] };
    let savedTripleCount = 0;
    
    if (triplesForProcessing.length > 0) {
      try {
        console.log(`💾 API: Saving ${triplesForProcessing.length} triples to graph database...`);
        
        // Get the database type from settings
        const graphDbType = getGraphDbType() as GraphDBType;
        const graphDbService = getGraphDbService(graphDbType);
        
        // Initialize the service based on database type
        if (graphDbType === 'neo4j') {
          const uri = process.env.NEO4J_URI;
          const username = process.env.NEO4J_USER || process.env.NEO4J_USERNAME;
          const password = process.env.NEO4J_PASSWORD;
          graphDbService.initialize(uri, username, password);
        } else if (graphDbType === 'arangodb') {
          const url = process.env.MEMORY_SERVICE_URL || process.env.ARANGODB_URL || 'http://graph:8529';
          const dbName = process.env.ARANGODB_DB || 'project_vyasa';
          const username = process.env.ARANGODB_USER || 'root';
          const password = process.env.ARANGODB_PASSWORD || '';
          await (graphDbService as any).initialize(url, dbName, username, password);
        }
        
        // Import triples into the graph database
        await graphDbService.importTriples(triplesForProcessing);
        savedTripleCount = triplesForProcessing.length;
        console.log(`✅ API: Successfully saved ${savedTripleCount} triples to ${graphDbType}`);
        
        // Mark document as processed (for ArangoDB)
        if (graphDbType === 'arangodb' && documentId) {
          try {
            await (graphDbService as any).markDocumentAsProcessed(documentId, savedTripleCount);
            console.log(`✅ API: Marked document "${documentId}" as processed`);
          } catch (markError) {
            console.warn('⚠️ API: Failed to mark document as processed:', markError);
            // Don't fail the request if marking fails
          }
        }
        
        // Get graph data (nodes and edges) from the database
        try {
          graphData = await graphDbService.getGraphData();
          console.log(`✅ API: Retrieved graph data: ${graphData.nodes.length} nodes, ${graphData.relationships.length} edges`);
        } catch (graphError) {
          console.warn('⚠️ API: Failed to retrieve graph data:', graphError);
          // Continue with empty graph data
        }
      } catch (saveError) {
        console.error('❌ API: Failed to save triples to graph database:', saveError);
        // Continue execution - return what we have even if save failed
      }
    } else {
      console.warn('⚠️ API: No triples to save (empty extraction or no valid triples)');
    }

    // Return success response with documentId and graph data
    return NextResponse.json({
      success: true,
      message: 'Document processed successfully',
      documentId,
      tripleCount: triplesForProcessing.length,
      savedTripleCount,
      triples: triplesForProcessing,
      graph: {
        nodes: graphData.nodes,
        edges: graphData.relationships
      },
      documentName: filename || documentId,
      langchainUsed: useLangChain,
      graphTransformerUsed: useGraphTransformer,
      customPromptsUsed: !!(systemPrompt || extractionPrompt || graphTransformerPrompt),
      graphDbType: getGraphDbType()
    });
  } catch (error) {
    console.error('Error processing document:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { error: `Failed to process document: ${errorMessage}` },
      { status: 500 }
    );
  }
} 
