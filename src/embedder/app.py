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
import os
import time
import sys
import threading
from queue import Queue, Empty
from pathlib import Path
from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent))

from shared.logger import get_logger  # noqa: E402
from shared.config import EMBEDDING_MODEL_PATH, HF_TOKEN  # noqa: E402

logger = get_logger("embedder", __name__)

app = Flask(__name__)

# Get model path from shared config
model_name = EMBEDDING_MODEL_PATH
logger.info(f"Loading embedding model: {model_name}")

# Force CUDA on GB10; fallback handled on error
device = "cuda"
logger.info(f"Using device: {device}")

# Load model during startup with CUDA support if available
start_time = time.time()
try:
    if device == "cuda":
        import torch
        logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")
    
    # Load model on appropriate device with HF_TOKEN for authenticated downloads
    model_kwargs = {"device": device}
    if HF_TOKEN:
        model_kwargs["token"] = HF_TOKEN
        logger.info("Using HF_TOKEN for authenticated model download")
    
model = SentenceTransformer(model_name, **model_kwargs)
    logger.info(f"Model loaded in {time.time() - start_time:.2f} seconds on {device}")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    # Fallback to CPU if CUDA fails
    if device == "cuda":
        try:
            logger.warning("Falling back to CPU")
            model_kwargs = {"device": "cpu"}
            if HF_TOKEN:
                model_kwargs["token"] = HF_TOKEN
            model = SentenceTransformer(model_name, **model_kwargs)
            logger.info(f"Model loaded on CPU in {time.time() - start_time:.2f} seconds")
        except Exception as e2:
            logger.error(f"Failed to load model on CPU: {e2}")
            raise
    else:
        raise

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "model": model_name})

class BatchingQueue:
    """Simple batching queue to coalesce embed requests."""

    def __init__(self, max_batch: int = 32, flush_ms: int = 500):
        self.max_batch = max_batch
        self.flush_ms = flush_ms / 1000.0
        self.queue: Queue[tuple[list[str], threading.Event, dict]] = Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def enqueue(self, texts: list[str]) -> list[list[float]]:
        done = threading.Event()
        slot: dict = {}
        self.queue.put((texts, done, slot))
        done.wait()
        return slot["result"]  # type: ignore[index]

    def _worker(self):
        while True:
            batch = []
            events = []
            slots = []
            start_time = time.time()
            try:
                item = self.queue.get(timeout=0.1)
                texts, evt, slot = item
                batch.extend(texts)
                events.append(evt)
                slots.append((slot, len(texts)))
            except Empty:
                continue
            while len(batch) < self.max_batch and (time.time() - start_time) < self.flush_ms:
                try:
                    texts, evt, slot = self.queue.get(timeout=0.01)
                    batch.extend(texts)
                    events.append(evt)
                    slots.append((slot, len(texts)))
                except Empty:
                    continue
            try:
                embeddings = model.encode(batch, batch_size=self.max_batch).tolist()
                idx = 0
                for (slot, count) in slots:
                    slot["result"] = embeddings[idx: idx + count]
                    idx += count
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Batch encode failed: {exc}")
                for (slot, count) in slots:
                    slot["result"] = [[]] * count
            finally:
                for evt in events:
                    evt.set()


batcher = BatchingQueue(max_batch=32, flush_ms=500)


@app.route("/embed", methods=["POST"])
def embed():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        texts = data.get("texts", [])
        if not texts:
            return jsonify({"error": "No texts provided"}), 400
            
        start_time = time.time()
        embeddings = batcher.enqueue(texts)
        processing_time = time.time() - start_time
        
        logger.info(f"Batched embed: {len(texts)} texts in {processing_time:.2f} seconds")
        
        return jsonify({
            "embeddings": embeddings,
            "model": model_name,
            "processing_time": processing_time
        })
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return jsonify({"error": str(e)}), 500

# Add compatibility with the /embeddings endpoint for the EmbeddingsService class
@app.route("/embeddings", methods=["POST"])
def embeddings():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        texts = data.get("input", [])
        if not texts:
            return jsonify({"error": "No input texts provided"}), 400
            
        start_time = time.time()
        embeddings = batcher.enqueue(texts)
        processing_time = time.time() - start_time
        
        # Format response for compatibility with the EmbeddingsService
        response_data = {
            "data": [{"embedding": embedding} for embedding in embeddings],
            "model": model_name,
            "processing_time": processing_time
        }
        
        logger.info(f"Processed {len(texts)} texts in {processing_time:.2f} seconds for /embeddings endpoint")
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80))) 
