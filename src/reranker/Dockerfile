# Reranker service for Project Vyasa
# NeMo Retriever Text Reranking NIM: llama-3.2-nv-rerankqa-1b-v2
FROM python:3.11-slim

WORKDIR /app

# Default model can be overridden at build time
ARG MODEL_NAME=nvidia/llama-3.2-nv-rerankqa-1b-v2

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py /app/

# Set default model name
ENV MODEL_NAME="${MODEL_NAME}"
ENV RERANKER_MODEL_ID="${MODEL_NAME}"
ENV HF_HOME="/raid/vyasa/hf_cache"

# Expose the port
EXPOSE 30011

# Use Gunicorn for better performance
CMD ["gunicorn", "--bind", "0.0.0.0:30011", "--workers", "1", "--threads", "8", "app:app"]
