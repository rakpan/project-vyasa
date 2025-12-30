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
 * TypeScript types matching the Pydantic models in src/shared/schema.py
 * 
 * These types ensure type safety between the frontend and Cortex backend.
 */

export type RelationType = 'MITIGATES' | 'ENABLES' | 'REQUIRES';

export type EntityType = 'Vulnerability' | 'Mechanism' | 'Constraint' | 'Outcome';

export interface Vulnerability {
  _id?: string;
  _key?: string;
  name: string;
  description: string;
  severity?: string;
  category?: string;
  source?: string;
}

export interface Mechanism {
  _id?: string;
  _key?: string;
  name: string;
  description: string;
  mechanism_type?: string;
  source?: string;
}

export interface Constraint {
  _id?: string;
  _key?: string;
  name: string;
  description: string;
  constraint_type?: string;
  source?: string;
}

export interface Outcome {
  _id?: string;
  _key?: string;
  name: string;
  description: string;
  outcome_type?: string;
  source?: string;
}

export interface GraphTriple {
  subject: string;
  predicate: RelationType;
  object: string;
  subject_type: EntityType;
  object_type: EntityType;
  confidence?: number; // 0.0 to 1.0
  evidence?: string;    // The source text snippet
  source?: string;
}

export interface KnowledgeGraph {
  vulnerabilities: Vulnerability[];
  mechanisms: Mechanism[];
  constraints: Constraint[];
  outcomes: Outcome[];
  triples: GraphTriple[];
  source?: string;
}

// Legacy Triple interface for backward compatibility
// Maps to GraphTriple but without entity type fields
export interface Triple {
  subject: string;
  predicate: string;
  object: string;
  confidence?: number; // 0.0 to 1.0
  evidence?: string;  // The source text snippet
  usedFallback?: boolean;
}

/**
 * Convert KnowledgeGraph triples to legacy Triple format for UI compatibility
 */
export function knowledgeTriplesToLegacy(triples: GraphTriple[]): Triple[] {
  return triples.map(triple => ({
    subject: triple.subject,
    predicate: triple.predicate,
    object: triple.object,
    confidence: triple.confidence,
    evidence: triple.evidence,
  }));
}

/**
 * Convert legacy Triple format to KnowledgeGraph GraphTriple (with defaults)
 */
export function legacyTriplesToKnowledge(triples: Triple[]): GraphTriple[] {
  return triples.map(triple => ({
    subject: triple.subject,
    predicate: (triple.predicate as RelationType) || 'ENABLES',
    object: triple.object,
    subject_type: 'Mechanism', // Default, should be inferred
    object_type: 'Outcome', // Default, should be inferred
    confidence: triple.confidence,
    evidence: triple.evidence,
  }));
}

// Legacy aliases for backward compatibility (deprecated)
/** @deprecated Use KnowledgeGraph instead */
export type PACTGraph = KnowledgeGraph;
/** @deprecated Use knowledgeTriplesToLegacy instead */
export const pactTriplesToLegacy = knowledgeTriplesToLegacy;
/** @deprecated Use legacyTriplesToKnowledge instead */
export const legacyTriplesToPACT = legacyTriplesToKnowledge;

