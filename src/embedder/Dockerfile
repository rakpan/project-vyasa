# Embedder service for Project Vyasa
# Supports both CUDA (if available) and CPU fallback
FROM python:3.11-slim

WORKDIR /app

# Default model can be overridden at build time with --build-arg MODEL_NAME=...
ARG MODEL_NAME=BAAI/bge-large-en-v1.5

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
# PyTorch will auto-detect CUDA at runtime if available
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py /app/

# Set default model name
ENV MODEL_NAME="${MODEL_NAME}"
ENV EMBEDDING_MODEL_PATH="${MODEL_NAME}"
ENV TRANSFORMERS_CACHE="/app/.cache"
ENV HF_HOME="/app/.cache"

# Pre-download the model during build for faster startup
# This will use CPU during build, but runtime will detect CUDA if available
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${MODEL_NAME}')"

# Expose the port
EXPOSE 80

# Use Gunicorn for better performance
# The app will automatically detect and use CUDA if available at runtime
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "1", "--threads", "8", "app:app"] 
