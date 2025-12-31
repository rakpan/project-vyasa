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
// ArangoDB initialization script for Project Vyasa
// This script creates the project_vyasa database and required collections
// Mount this file into the ArangoDB container at /docker-entrypoint-initdb.d/arango-init.js

const db = require('@arangodb').db;
const systemDb = require('@arangodb').db._system();

// Database name
const DB_NAME = 'project_vyasa';

try {
  // Check if database already exists
  const databases = systemDb._databases();
  if (databases.includes(DB_NAME)) {
    console.log(`Database '${DB_NAME}' already exists, skipping creation`);
  } else {
    // Create the database
    systemDb._createDatabase(DB_NAME);
    console.log(`✅ Database '${DB_NAME}' created successfully!`);
  }

  // Switch to the project_vyasa database
  db._useDatabase(DB_NAME);

  // Create collections required by Project Vyasa
  const collections = [
    {
      name: 'entities',
      type: 'document',
      description: 'Entity collection for knowledge graph (Vulnerabilities, Mechanisms, Constraints, Outcomes)'
    },
    {
      name: 'edges',
      type: 'edge',
      description: 'Edge collection for graph relationships (MITIGATES, ENABLES, REQUIRES)'
    },
    {
      name: 'documents',
      type: 'document',
      description: 'Document metadata collection'
    },
    {
      name: 'projects',
      type: 'document',
      description: 'Project configurations (Thesis, RQs, Anti-Scope, Seed Corpus)'
    },
    {
      name: 'manuscript_blocks',
      type: 'document',
      description: 'Manuscript blocks with version history and citation binding'
    },
    {
      name: 'patches',
      type: 'document',
      description: 'Proposed edits (patches) for manuscript blocks awaiting review'
    },
    {
      name: 'project_bibliography',
      type: 'document',
      description: 'Project bibliography for citation validation (Librarian Key-Guard)'
    },
    {
      name: 'canonical_knowledge',
      type: 'document',
      description: 'Global repository of expert-vetted, merged knowledge with provenance tracking'
    },
    {
      name: 'node_aliases',
      type: 'document',
      description: 'Alias relationships for merged graph nodes (used by /extractions/merge endpoint)'
    },
    {
      name: 'pdf_text_cache',
      type: 'document',
      description: 'Cached PDF page text layers for evidence verification (keyed by doc_hash and page)'
    }
  ];

  // Create collections if they don't exist
  for (const coll of collections) {
    if (!db._collection(coll.name)) {
      if (coll.type === 'edge') {
        db._createEdgeCollection(coll.name);
      } else {
        db._createDocumentCollection(coll.name);
      }
      console.log(`✅ Collection '${coll.name}' (${coll.type}) created`);
    } else {
      console.log(`Collection '${coll.name}' already exists, skipping`);
    }
  }

  // Create indexes for better query performance
  const entitiesCollection = db._collection('entities');
  if (entitiesCollection) {
    // Index on name for faster lookups
    try {
      entitiesCollection.ensureIndex({
        type: 'persistent',
        fields: ['name'],
        unique: false
      });
      console.log('✅ Index created on entities.name');
    } catch (e) {
      // Index might already exist
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on entities.name: ${e.message}`);
      }
    }

    // Index on type for filtering by entity type
    try {
      entitiesCollection.ensureIndex({
        type: 'persistent',
        fields: ['type'],
        unique: false
      });
      console.log('✅ Index created on entities.type');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on entities.type: ${e.message}`);
      }
    }
  }

  const edgesCollection = db._collection('edges');
  if (edgesCollection) {
    // Index on type/predicate for faster relationship queries
    try {
      edgesCollection.ensureIndex({
        type: 'persistent',
        fields: ['type'],
        unique: false
      });
      console.log('✅ Index created on edges.type');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on edges.type: ${e.message}`);
      }
    }
  }

  const canonicalCollection = db._collection('canonical_knowledge');
  if (canonicalCollection) {
    // Unique identifier for canonical entries
    try {
      canonicalCollection.ensureIndex({
        type: 'persistent',
        fields: ['entity_id'],
        unique: true
      });
      console.log('✅ Index created on canonical_knowledge.entity_id (unique)');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on canonical_knowledge.entity_id: ${e.message}`);
      }
    }

    // Lookup helpers
    const canonicalIndexes = [
      { fields: ['entity_name'], unique: false },
      { fields: ['entity_type'], unique: false },
      { fields: ['conflict_flags[*]'], unique: false },
      { fields: ['provenance_log[*].project_id'], unique: false },
      { fields: ['provenance_log[*].job_id'], unique: false },
      { fields: ['source_pointers[*].doc_hash'], unique: false },
    ];

    for (const idx of canonicalIndexes) {
      try {
        canonicalCollection.ensureIndex({ type: 'persistent', ...idx });
        console.log(`✅ Index created on canonical_knowledge.${idx.fields.join(',')}`);
      } catch (e) {
        if (!e.message.includes('already exists')) {
          console.warn(`Warning creating index on canonical_knowledge.${idx.fields.join(',')}: ${e.message}`);
        }
      }
    }
  }

  // Create indexes for node_aliases collection
  const aliasesCollection = db._collection('node_aliases');
  if (aliasesCollection) {
    try {
      aliasesCollection.ensureIndex({
        type: 'persistent',
        fields: ['source_node_id'],
        unique: false
      });
      console.log('✅ Index created on node_aliases.source_node_id');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on node_aliases.source_node_id: ${e.message}`);
      }
    }

    try {
      aliasesCollection.ensureIndex({
        type: 'persistent',
        fields: ['target_node_id'],
        unique: false
      });
      console.log('✅ Index created on node_aliases.target_node_id');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on node_aliases.target_node_id: ${e.message}`);
      }
    }
  }

  // Create indexes for pdf_text_cache collection
  const pdfCacheCollection = db._collection('pdf_text_cache');
  if (pdfCacheCollection) {
    try {
      pdfCacheCollection.ensureIndex({
        type: 'persistent',
        fields: ['doc_hash', 'page'],
        unique: true
      });
      console.log('✅ Index created on pdf_text_cache.doc_hash,page (unique)');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on pdf_text_cache.doc_hash,page: ${e.message}`);
      }
    }
  }

  // Create indexes for manuscript_blocks collection
  const manuscriptCollection = db._collection('manuscript_blocks');
  if (manuscriptCollection) {
    try {
      manuscriptCollection.ensureIndex({
        type: 'persistent',
        fields: ['project_id', 'block_id', 'version'],
        unique: true
      });
      console.log('✅ Index created on manuscript_blocks.project_id,block_id,version (unique)');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on manuscript_blocks.project_id,block_id,version: ${e.message}`);
      }
    }

    try {
      manuscriptCollection.ensureIndex({
        type: 'persistent',
        fields: ['project_id'],
        unique: false
      });
      console.log('✅ Index created on manuscript_blocks.project_id');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on manuscript_blocks.project_id: ${e.message}`);
      }
    }
  }

  // Create indexes for projects collection
  const projectsCollection = db._collection('projects');
  if (projectsCollection) {
    try {
      projectsCollection.ensureIndex({
        type: 'persistent',
        fields: ['created_at'],
        unique: false
      });
      console.log('✅ Index created on projects.created_at');
    } catch (e) {
      if (!e.message.includes('already exists')) {
        console.warn(`Warning creating index on projects.created_at: ${e.message}`);
      }
    }
  }

  console.log(`✅ ArangoDB initialization complete for '${DB_NAME}'`);
} catch (error) {
  console.error(`❌ Error during ArangoDB initialization: ${error.message}`);
  console.error(error.stack);
  throw error;
}
