#!/bin/sh
#
# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Script to initialize Qdrant collections for Project Vyasa
# Target container: vyasa-qdrant (port 6333)
# Collections: entity-embeddings, document-embeddings

echo "Initializing Qdrant collections for Project Vyasa..."

# Wait for the Qdrant service to become available
echo "Waiting for vyasa-qdrant service to start..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
  if curl -s http://vyasa-qdrant:6333/healthz > /dev/null; then
    echo "Qdrant service is up!"
    break
  fi
  echo "Waiting for vyasa-qdrant service (attempt $attempt/$max_attempts)..."
  attempt=$((attempt + 1))
  sleep 2
done

if [ $attempt -gt $max_attempts ]; then
  echo "Timed out waiting for vyasa-qdrant service"
  exit 1
fi

# Function to create collection if it doesn't exist
create_collection() {
  local collection_name=$1
  local vector_size=$2
  
  echo "Checking if collection '${collection_name}' exists..."
  COLLECTION_EXISTS=$(curl -s "http://vyasa-qdrant:6333/collections/${collection_name}" | grep -c '"status":"ok"' || echo "0")

  if [ "$COLLECTION_EXISTS" -gt "0" ]; then
    echo "Collection '${collection_name}' already exists, skipping creation"
  else
    echo "Creating collection '${collection_name}'..."
    RESPONSE=$(curl -s -X PUT "http://vyasa-qdrant:6333/collections/${collection_name}" \
      -H "Content-Type: application/json" \
      -d "{
        \"vectors\": {
          \"size\": ${vector_size},
          \"distance\": \"Cosine\"
        }
      }")

    if echo "$RESPONSE" | grep -q '"status":"ok"'; then
      echo "✅ Collection '${collection_name}' created successfully"
    else
      echo "❌ Failed to create collection '${collection_name}'"
      echo "Response: $RESPONSE"
      exit 1
    fi
  fi
}

# Create entity-embeddings collection (384 dimensions for all-MiniLM-L6-v2)
create_collection "entity-embeddings" 384

# Create document-embeddings collection (384 dimensions for all-MiniLM-L6-v2)
create_collection "document-embeddings" 384

echo "✅ Qdrant initialization complete - both collections ready"
