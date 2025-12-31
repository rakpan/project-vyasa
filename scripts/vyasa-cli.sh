#!/bin/bash
# Project Vyasa - Operational CLI Helper
# Description : Convenience wrapper for common operations (start/stop/logs/etc).
# Dependencies: docker, curl
# Usage      : ./scripts/vyasa-cli.sh <command> [args...]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-http://localhost:8000}"

# ============================================
# Command: merge
# ============================================
# Merges two graph nodes by creating an alias relationship.
# This is used to consolidate duplicate entities in the knowledge graph.
#
# Usage: ./scripts/vyasa-cli.sh merge <job_id> <source_id> <target_id>
#
merge_command() {
    local job_id="$1"
    local source_id="$2"
    local target_id="$3"
    
    if [ -z "$job_id" ] || [ -z "$source_id" ] || [ -z "$target_id" ]; then
        echo "Error: merge command requires job_id, source_id, and target_id"
        echo "Usage: ./scripts/vyasa-cli.sh merge <job_id> <source_id> <target_id>"
        exit 1
    fi
    
    echo "Merging nodes for job: $job_id"
    echo "  Source: $source_id"
    echo "  Target: $target_id"
    echo ""
    
    response=$(curl -s -X PATCH "$ORCHESTRATOR_URL/jobs/$job_id/extractions/merge" \
        -H "Content-Type: application/json" \
        -d "{
            \"source_node_id\": \"$source_id\",
            \"target_node_id\": \"$target_id\"
        }")
    
    if echo "$response" | grep -q '"status":"merged"'; then
        echo "✓ Merge successful"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        echo "✗ Merge failed"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        exit 1
    fi
}

# ============================================
# Main Command Router
# ============================================
case "${1:-help}" in
    merge)
        if [ $# -lt 4 ]; then
            echo "Error: merge command requires 3 arguments"
            echo "Usage: ./scripts/vyasa-cli.sh merge <job_id> <source_id> <target_id>"
            exit 1
        fi
        merge_command "$2" "$3" "$4"
        ;;
    help|--help|-h)
        echo "Project Vyasa - Operational CLI Helper"
        echo ""
        echo "Usage: ./scripts/vyasa-cli.sh <command> [args...]"
        echo ""
        echo "Commands:"
        echo "  merge <job_id> <source_id> <target_id>"
        echo "    Merge two graph nodes by creating an alias relationship."
        echo "    Calls PATCH /jobs/<job_id>/extractions/merge endpoint."
        echo "    This consolidates duplicate entities in the knowledge graph."
        echo ""
        echo "  help"
        echo "    Show this help message."
        echo ""
        echo "Environment Variables:"
        echo "  ORCHESTRATOR_URL  Base URL for Orchestrator API (default: http://localhost:8000)"
        echo ""
        echo "Examples:"
        echo "  ./scripts/vyasa-cli.sh merge job-123 entity_1 entity_2"
        ;;
    *)
        echo "Error: Unknown command '$1'"
        echo "Run './scripts/vyasa-cli.sh help' for usage information"
        exit 1
        ;;
esac
