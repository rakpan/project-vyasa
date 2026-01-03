#!/bin/bash
# Setup script for orchestrator container
# Creates minimal CUDA header stubs to satisfy torch_memory_saver build requirements
# The orchestrator doesn't actually use CUDA at runtime - it just makes HTTP requests

set -e

# Install build dependencies
apt-get update
apt-get install -y build-essential g++
rm -rf /var/lib/apt/lists/*

# Create minimal CUDA header stubs to satisfy torch_memory_saver build
# The compiler uses #include <cuda_runtime_api.h> which searches system include paths
# Place the header in /usr/include (standard system include path)
mkdir -p /usr/local/cuda/include
mkdir -p /usr/include

# Create the header file
cat > /usr/include/cuda_runtime_api.h << 'EOF'
#ifndef CUDA_RUNTIME_API_H
#define CUDA_RUNTIME_API_H

#include <stddef.h>

typedef int cudaError_t;
typedef void* cudaStream_t;

#define cudaSuccess 0
#define cudaMemcpyHostToDevice 1
#define cudaMemcpyDeviceToHost 2
#define cudaMemcpyDeviceToDevice 3

cudaError_t cudaMalloc(void** ptr, size_t size);
cudaError_t cudaFree(void* ptr);
cudaError_t cudaMemcpy(void* dst, const void* src, size_t count, int kind);
cudaError_t cudaStreamCreate(cudaStream_t* stream);
cudaError_t cudaStreamDestroy(cudaStream_t stream);

#endif
EOF

# Also create in /usr/local/cuda/include for CUDA_HOME compatibility
cp /usr/include/cuda_runtime_api.h /usr/local/cuda/include/cuda_runtime_api.h

# Set environment variables to help the build find CUDA headers
export CUDA_HOME=/usr/local/cuda
export CUDA_PATH=/usr/local/cuda
export C_INCLUDE_PATH=/usr/include:/usr/local/cuda/include:$C_INCLUDE_PATH
export CPLUS_INCLUDE_PATH=/usr/include:/usr/local/cuda/include:$CPLUS_INCLUDE_PATH
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt

# Start uvicorn
exec uvicorn src.orchestrator.main:app --host 0.0.0.0 --port 8000
