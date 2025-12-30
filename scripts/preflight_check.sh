#!/bin/bash
#
# Preflight Check for Project Vyasa on DGX Spark (GB10)
#
# Validates hardware, memory, configuration, and port availability
# before launching the stack.
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Status tracking
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

echo "=========================================="
echo "Project Vyasa - Preflight Check"
echo "DGX Spark (GB10) Validation"
echo "=========================================="
echo ""

# ============================================
# Check 1: NVIDIA GPU Detection (GB10 Superchip)
# ============================================
echo -n "Checking NVIDIA GB10 superchip detection... "

if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}FAIL${NC}"
    echo "  Error: nvidia-smi not found. NVIDIA drivers may not be installed."
    ((CHECKS_FAILED++))
else
    # Check if nvidia-smi can see any GPUs
    GPU_COUNT=$(nvidia-smi --list-gpus 2>/dev/null | wc -l || echo "0")
    
    if [ "$GPU_COUNT" -eq "0" ]; then
        echo -e "${RED}FAIL${NC}"
        echo "  Error: nvidia-smi cannot detect any GPUs."
        echo "  Ensure NVIDIA drivers are installed and GB10 is properly connected."
        ((CHECKS_FAILED++))
    else
        # Check for GB10-specific identifiers
        # GB10 may show as "Grace Hopper" or "GH200" in nvidia-smi
        GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 || echo "")
        
        if echo "$GPU_INFO" | grep -qiE "(Grace|Hopper|GH200|GB10|Blackwell)"; then
            echo -e "${GREEN}PASS${NC}"
            echo "  Detected: $GPU_INFO"
            echo "  GPU Count: $GPU_COUNT"
            ((CHECKS_PASSED++))
        else
            echo -e "${YELLOW}WARN${NC}"
            echo "  Warning: GPU detected but may not be GB10 superchip."
            echo "  GPU Info: $GPU_INFO"
            echo "  Continuing with validation..."
            ((WARNINGS++))
            ((CHECKS_PASSED++))
        fi
    fi
fi
echo ""

# ============================================
# Check 2: Unified Memory Verification
# ============================================
echo -n "Checking unified memory (minimum 120GB required)... "

if ! command -v free &> /dev/null; then
    echo -e "${RED}FAIL${NC}"
    echo "  Error: 'free' command not found."
    ((CHECKS_FAILED++))
else
    # Get total memory in GB
    # free -h outputs in human-readable format, we need to parse it
    MEM_TOTAL_KB=$(free -k | awk '/^Mem:/ {print $2}')
    MEM_TOTAL_GB=$((MEM_TOTAL_KB / 1024 / 1024))
    
    if [ "$MEM_TOTAL_GB" -ge "120" ]; then
        echo -e "${GREEN}PASS${NC}"
        echo "  Total Unified Memory: ${MEM_TOTAL_GB}GB"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Error: Insufficient unified memory detected."
        echo "  Required: 120GB minimum"
        echo "  Detected: ${MEM_TOTAL_GB}GB"
        echo "  DGX Spark GB10 should have 128GB unified memory."
        ((CHECKS_FAILED++))
    fi
fi
echo ""

# ============================================
# Check 3: Expertise Configuration File
# ============================================
echo -n "Checking for expertise configuration... "

EXPERTISE_FILE="data/private/expertise.json"

if [ -f "$EXPERTISE_FILE" ]; then
    echo -e "${GREEN}PASS${NC}"
    echo "  Found: $EXPERTISE_FILE"
    echo "  Using custom expert prompts."
    ((CHECKS_PASSED++))
else
    echo -e "${YELLOW}WARN${NC}"
    echo "  Warning: $EXPERTISE_FILE not found."
    echo "  The system will use generic prompts instead of expert-tuned prompts."
    echo "  To enable expert prompts, create $EXPERTISE_FILE with your domain expertise."
    ((WARNINGS++))
    ((CHECKS_PASSED++))
fi
echo ""

# ============================================
# Check 4: Port Availability
# ============================================
echo "Checking port availability..."

PORTS_TO_CHECK=(
    "30000:Brain (Cortex)"
    "30001:Worker (Cortex)"
    "8529:Memory (ArangoDB)"
)

PORT_CONFLICTS=0

for PORT_INFO in "${PORTS_TO_CHECK[@]}"; do
    PORT=$(echo "$PORT_INFO" | cut -d: -f1)
    SERVICE=$(echo "$PORT_INFO" | cut -d: -f2)
    
    echo -n "  Port $PORT ($SERVICE)... "
    
    # Check if port is in use
    if command -v nc &> /dev/null; then
        # Using netcat (nc) if available
        if nc -z localhost "$PORT" 2>/dev/null; then
            echo -e "${RED}CONFLICT${NC}"
            echo "    Error: Port $PORT is already in use."
            echo "    Stop the conflicting service before launching Project Vyasa."
            ((PORT_CONFLICTS++))
            ((CHECKS_FAILED++))
        else
            echo -e "${GREEN}AVAILABLE${NC}"
            ((CHECKS_PASSED++))
        fi
    elif command -v ss &> /dev/null; then
        # Using ss (socket statistics) as fallback
        if ss -tuln | grep -q ":$PORT "; then
            echo -e "${RED}CONFLICT${NC}"
            echo "    Error: Port $PORT is already in use."
            echo "    Stop the conflicting service before launching Project Vyasa."
            ((PORT_CONFLICTS++))
            ((CHECKS_FAILED++))
        else
            echo -e "${GREEN}AVAILABLE${NC}"
            ((CHECKS_PASSED++))
        fi
    elif command -v lsof &> /dev/null; then
        # Using lsof as another fallback
        if lsof -i ":$PORT" &>/dev/null; then
            echo -e "${RED}CONFLICT${NC}"
            echo "    Error: Port $PORT is already in use."
            echo "    Stop the conflicting service before launching Project Vyasa."
            ((PORT_CONFLICTS++))
            ((CHECKS_FAILED++))
        else
            echo -e "${GREEN}AVAILABLE${NC}"
            ((CHECKS_PASSED++))
        fi
    else
        echo -e "${YELLOW}SKIP${NC}"
        echo "    Warning: Cannot check port (nc/ss/lsof not available)."
        echo "    Manually verify ports $PORT are free before launching."
        ((WARNINGS++))
    fi
done
echo ""

# ============================================
# Summary
# ============================================
echo "=========================================="
echo "Preflight Check Summary"
echo "=========================================="
echo "  Passed:  ${CHECKS_PASSED}"
echo "  Failed:  ${CHECKS_FAILED}"
echo "  Warnings: ${WARNINGS}"
echo ""

if [ "$CHECKS_FAILED" -eq "0" ]; then
    echo -e "${GREEN}✓ Launch Ready${NC}"
    echo ""
    echo "All critical checks passed. You can proceed with:"
    echo "  docker compose -f deploy/docker-compose.yml up -d"
    exit 0
else
    echo -e "${RED}✗ Launch Blocked${NC}"
    echo ""
    echo "Critical checks failed. Please resolve the issues above before launching."
    if [ "$PORT_CONFLICTS" -gt "0" ]; then
        echo ""
        echo "To find processes using conflicting ports:"
        echo "  sudo lsof -i :30000  # Brain"
        echo "  sudo lsof -i :30001  # Worker"
        echo "  sudo lsof -i :8529   # ArangoDB"
    fi
    exit 1
fi

