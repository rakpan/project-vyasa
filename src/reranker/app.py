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
"""
Reranker service for Project Vyasa.

NeMo Retriever Text Reranking NIM: llama-3.2-nv-rerankqa-1b-v2
- Takes a query and a list of candidate documents
- Returns relevance scores for each document
- Used to refine top-K retrieval results to top-M evidence packets
"""
import os
import time
import sys
from pathlib import Path
from flask import Flask, request, jsonify
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent))

from shared.logger import get_logger  # noqa: E402
from shared.config import RERANKER_MODEL_ID, HF_TOKEN  # noqa: E402

logger = get_logger("reranker", __name__)

app = Flask(__name__)

# Get model path from shared config
model_name = RERANKER_MODEL_ID
logger.info(f"Loading reranker model: {model_name}")

# Load model during startup
start_time = time.time()
model = None

try:
    from sentence_transformers import CrossEncoder
    
    device = "cuda" if os.environ.get("NVIDIA_VISIBLE_DEVICES") else "cpu"
    logger.info(f"Using device: {device}")
    
    if device == "cuda":
        import torch
        logger.info(f"CUDA device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
    
    # Load CrossEncoder model (NeMo Retriever reranker models use CrossEncoder)
    model_kwargs = {"device": device}
    if HF_TOKEN:
        model_kwargs["token"] = HF_TOKEN
        logger.info("Using HF_TOKEN for authenticated model download")
    
    model = CrossEncoder(model_name, **model_kwargs)
    logger.info(f"Model loaded in {time.time() - start_time:.2f} seconds on {device}")
except Exception as e:
    logger.error(f"Failed to load reranker model: {e}", exc_info=True)
    # Fallback to CPU if CUDA fails
    if device == "cuda":
        try:
            logger.warning("Falling back to CPU")
            model_kwargs = {"device": "cpu"}
            if HF_TOKEN:
                model_kwargs["token"] = HF_TOKEN
            model = CrossEncoder(model_name, **model_kwargs)
            logger.info(f"Model loaded on CPU in {time.time() - start_time:.2f} seconds")
        except Exception as e2:
            logger.error(f"Failed to load model on CPU: {e2}", exc_info=True)
            raise
    else:
        raise


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "model": model_name})


@app.route("/v1/ranking", methods=["POST"])
def ranking_v1():
    """
    OpenAI-style ranking endpoint.
    
    Request body:
    {
        "model": str,
        "query": str,
        "documents": List[Dict[str, Any]],  # Each dict should have "id", "text", "metadata"?
        "top_k": Optional[int]
    }
    
    Response:
    {
        "data": List[Dict[str, Any]],  # Sorted by score (descending)
        "model": str
    }
    
    Each result dict contains:
    - "id": str (from input document)
    - "text": str (from input document)
    - "score": float (relevance score)
    - "rank": int (1-based rank)
    - "metadata": Optional[Dict] (from input document)
    """
    if model is None:
        return jsonify({"error": "Model not loaded"}), 503
    
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        query = data.get("query")
        if not query or not isinstance(query, str):
            return jsonify({"error": "Query must be a non-empty string"}), 400
        
        documents = data.get("documents", [])
        if not documents or not isinstance(documents, list):
            return jsonify({"error": "Documents must be a non-empty list"}), 400
        
        top_k = data.get("top_k")
        if top_k is not None and (not isinstance(top_k, int) or top_k < 1):
            return jsonify({"error": "top_k must be a positive integer"}), 400
        
        start_time = time.time()
        
        # Normalize documents to (text, id, metadata) tuples
        doc_pairs = []
        for doc in documents:
            if isinstance(doc, dict):
                text = doc.get("text") or doc.get("content") or str(doc)
                doc_id = doc.get("id") or doc.get("chunk_id")
                metadata = {k: v for k, v in doc.items() if k not in ("text", "content", "id", "chunk_id")}
                doc_pairs.append((text, doc_id, metadata))
            else:
                doc_pairs.append((str(doc), None, {}))
        
        # Prepare pairs for CrossEncoder: (query, document)
        pairs = [[query, doc_text] for doc_text, _, _ in doc_pairs]
        
        # Get scores from CrossEncoder
        scores = model.predict(pairs)
        
        # Combine scores with metadata and sort
        results = []
        for idx, (score, (doc_text, doc_id, metadata)) in enumerate(zip(scores, doc_pairs)):
            result = {
                "text": doc_text,
                "score": float(score),
                "rank": idx + 1,
            }
            if doc_id:
                result["id"] = doc_id
            if metadata:
                result["metadata"] = metadata
            results.append(result)
        
        # Sort by score (descending)
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Update ranks after sorting
        for idx, result in enumerate(results):
            result["rank"] = idx + 1
        
        # Apply top_k if specified
        if top_k is not None:
            results = results[:top_k]
        
        processing_time = time.time() - start_time
        
        logger.info(f"Ranked {len(documents)} documents → {len(results)} results in {processing_time:.2f} seconds")
        
        return jsonify({
            "data": results,
            "model": data.get("model", model_name),
            "processing_time": processing_time,
        })
    except Exception as e:
        logger.error(f"Error ranking: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/rerank", methods=["POST"])
def rerank():
    """
    Rerank candidate documents by relevance to a query.
    
    Request body:
    {
        "query": str,
        "documents": List[str] | List[Dict[str, Any]],
        "top_k": Optional[int]  # Default: return all, sorted by score
    }
    
    If documents is List[str], each string is treated as document text.
    If documents is List[Dict], each dict should have "text" field (and optionally "id", "metadata").
    
    Response:
    {
        "results": List[Dict[str, Any]],  # Sorted by score (descending)
        "model": str,
        "processing_time": float
    }
    
    Each result dict contains:
    - "text": str (document text)
    - "score": float (relevance score)
    - "rank": int (1-based rank)
    - "id": Optional[str] (if provided in input)
    - "metadata": Optional[Dict] (if provided in input)
    """
    if model is None:
        return jsonify({"error": "Model not loaded"}), 503
    
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        query = data.get("query")
        if not query or not isinstance(query, str):
            return jsonify({"error": "Query must be a non-empty string"}), 400
        
        documents = data.get("documents", [])
        if not documents or not isinstance(documents, list):
            return jsonify({"error": "Documents must be a non-empty list"}), 400
        
        top_k = data.get("top_k")
        if top_k is not None and (not isinstance(top_k, int) or top_k < 1):
            return jsonify({"error": "top_k must be a positive integer"}), 400
        
        start_time = time.time()
        
        # Normalize documents to (text, metadata) tuples
        doc_pairs = []
        for doc in documents:
            if isinstance(doc, str):
                doc_pairs.append((doc, {}))
            elif isinstance(doc, dict):
                text = doc.get("text") or doc.get("content") or str(doc)
                metadata = {k: v for k, v in doc.items() if k not in ("text", "content")}
                doc_pairs.append((text, metadata))
            else:
                doc_pairs.append((str(doc), {}))
        
        # Prepare pairs for CrossEncoder: (query, document)
        pairs = [[query, doc_text] for doc_text, _ in doc_pairs]
        
        # Get scores from CrossEncoder
        scores = model.predict(pairs)
        
        # Combine scores with metadata and sort
        results = []
        for idx, (score, (doc_text, metadata)) in enumerate(zip(scores, doc_pairs)):
            result = {
                "text": doc_text,
                "score": float(score),
                "rank": idx + 1,
            }
            if metadata:
                if "id" in metadata:
                    result["id"] = metadata["id"]
                if "chunk_id" in metadata:
                    result["chunk_id"] = metadata["chunk_id"]
                # Preserve other metadata
                other_meta = {k: v for k, v in metadata.items() if k not in ("id", "chunk_id")}
                if other_meta:
                    result["metadata"] = other_meta
            results.append(result)
        
        # Sort by score (descending)
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Update ranks after sorting
        for idx, result in enumerate(results):
            result["rank"] = idx + 1
        
        # Apply top_k if specified
        if top_k is not None:
            results = results[:top_k]
        
        processing_time = time.time() - start_time
        
        logger.info(f"Reranked {len(documents)} documents → {len(results)} results in {processing_time:.2f} seconds")
        
        return jsonify({
            "results": results,
            "model": model_name,
            "processing_time": processing_time,
            "query": query,
            "total_candidates": len(documents),
            "returned": len(results)
        })
    except Exception as e:
        logger.error(f"Error reranking: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 30011)))
