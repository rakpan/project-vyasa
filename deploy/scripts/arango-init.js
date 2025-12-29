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
      description: 'Entity collection for PACT ontology (Vulnerabilities, Mechanisms, Constraints, Outcomes)'
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

  console.log(`✅ ArangoDB initialization complete for '${DB_NAME}'`);
} catch (error) {
  console.error(`❌ Error during ArangoDB initialization: ${error.message}`);
  console.error(error.stack);
  throw error;
}

