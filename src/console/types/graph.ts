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
 * Triple interface representing a knowledge graph edge
 * Matches the backend schema from src/shared/schema.py
 */
export interface Triple {
  subject: string
  predicate: string
  object: string
  confidence?: number // 0.0 to 1.0
  evidence?: string    // The source text snippet
  usedFallback?: boolean
}

/**
 * Graph node interface matching ArangoDB entity structure
 * Compatible with Pydantic models from src/shared/schema.py
 */
export interface GraphNode {
  id: string;
  name: string;
  group?: string;
  type?: 'Vulnerability' | 'Mechanism' | 'Constraint' | 'Outcome';
  description?: string;
  _id?: string;
  _key?: string;
  [key: string]: any; // Allow additional properties
}

/**
 * Graph edge/relationship interface matching ArangoDB edge structure
 * Compatible with Pydantic GraphTriple model
 */
export interface GraphEdge {
  source: string;
  target: string;
  name?: string;
  type?: string;
  predicate?: 'MITIGATES' | 'ENABLES' | 'REQUIRES';
  confidence?: number;
  _id?: string;
  _from?: string;
  _to?: string;
  [key: string]: any; // Allow additional properties
}

/**
 * Graph data structure for visualization
 */
export interface GraphData {
  nodes: GraphNode[];
  links: GraphEdge[];
}

export interface VectorDBStats {
  nodes: number;
  relationships: number;
  source: string;
  httpHealthy?: boolean;
} 