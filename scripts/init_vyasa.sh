#!/bin/bash
set -e

# ==========================================
# PROJECT VYASA - INITIALIZATION SCRIPT
# ==========================================
# This script sets up the directory structure and 
# downloads the necessary NVIDIA playbooks for the fusion architecture.

PROJECT_NAME="project-vyasa"
NVIDIA_REPO_URL="https://github.com/NVIDIA/dgx-spark-playbooks.git"

echo "--> Initializing $PROJECT_NAME..."

# 1. Create Directory Structure
echo "--> Creating directory structure..."
mkdir -p $PROJECT_NAME/{deploy,src/ingestion,src/orchestrator,src/shared,notebooks,playbooks_ref}
cd $PROJECT_NAME

# 2. Fetch NVIDIA Playbooks (Reference Modules)
echo "--> Cloning NVIDIA DGX Spark Playbooks..."
# We clone to a temp directory to keep the workspace clean
git clone --depth 1 $NVIDIA_REPO_URL _temp_repo

echo "--> Extracting relevant modules..."
# Copy only the playbooks we need for the Fusion architecture
# Note: Path structure based on standard NVIDIA repo layout
cp -r _temp_repo/nvidia/txt2kg playbooks_ref/txt2kg 2>/dev/null || echo "Warning: txt2kg not found"
cp -r _temp_repo/nvidia/ollama playbooks_ref/ollama 2>/dev/null || echo "Warning: ollama not found"
cp -r _temp_repo/nvidia/build-and-deploy-a-multi-agent-chatbot playbooks_ref/multi-agent 2>/dev/null || echo "Warning: multi-agent not found"
cp -r _temp_repo/nvidia/sglang-inference-server playbooks_ref/sglang 2>/dev/null || echo "Warning: sglang not found"

# Clean up
rm -rf _temp_repo
echo "✓ Modules extracted to ./playbooks_ref/"


echo ""
echo "=========================================="
echo "PROJECT VYASA SETUP COMPLETE"
echo "=========================================="
echo "Location: $(pwd)"
echo ""
echo "Next Steps:"
echo "1. cd $PROJECT_NAME"
echo "2. make up            # Start the fusion stack"
echo "3. make logs          # Watch the supervisor load the model"
echo "4. open src/          # Start coding your orchestrator logic"
echo ""