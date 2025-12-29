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
"use client"

import { Network, Zap } from "lucide-react"
import { useDocuments } from "@/contexts/document-context"
import { Loader2 } from "lucide-react"

export function GraphActions() {
  const { documents, processDocuments, isProcessing, openGraphVisualization } = useDocuments()

  const hasNewDocuments = documents.some((doc) => doc.status === "New")
  const hasProcessedDocuments = documents.some(
    (doc) => doc.status === "Processed" && doc.triples && doc.triples.length > 0,
  )

  const handleProcessDocuments = async () => {
    try {
      // Get IDs of documents with "New" status
      const newDocumentIds = documents
        .filter(doc => doc.status === "New")
        .map(doc => doc.id);
        
      if (newDocumentIds.length === 0) {
        console.log("No new documents to process");
        return;
      }
      
      await processDocuments(newDocumentIds, {
        useLangChain: false,
        useGraphTransformer: false,
        promptConfigs: undefined
      });
    } catch (error) {
      console.error('Error processing documents:', error);
    }
  }

  return (
    <div className="flex gap-3 items-center">
      <button
        className={`btn-primary ${!hasNewDocuments || isProcessing ? "opacity-60 cursor-not-allowed" : ""}`}
        disabled={!hasNewDocuments || isProcessing}
        onClick={handleProcessDocuments}
      >
        {isProcessing ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Processing...
          </>
        ) : (
          <>
            <Zap className="h-4 w-4" />
            Process Documents
          </>
        )}
      </button>
      <button
        className={`btn-primary ${!hasProcessedDocuments || isProcessing ? "opacity-60 cursor-not-allowed" : ""}`}
        disabled={!hasProcessedDocuments || isProcessing}
        onClick={() => openGraphVisualization()}
      >
        <Network className="h-4 w-4" />
        View Knowledge Graph
      </button>
    </div>
  )
}

