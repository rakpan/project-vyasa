"""
Mock LLM Server for Project Vyasa.

Provides a FastAPI server that mimics the SGLang/OpenAI-compatible API for UI/Integration tests.
Allows running tests without GPU resources.

Usage:
    python -m src.mocks.server
    # Or use scripts/run_mock_llm.sh
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import json
import logging

app = FastAPI(title="Mock LLM Server", version="1.0.0")


def _detect_scenario(messages: List[Dict[str, str]]) -> str:
    """Detect which scenario to use based on system prompt.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'.
        
    Returns:
        Scenario name: 'cartographer', 'critic', or 'default'.
    """
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "").lower()
            if "cartographer" in content:
                return "cartographer"
            elif "critic" in content:
                return "critic"
    return "default"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    """Mock OpenAI/SGLang chat completions endpoint.
    
    Detects scenario based on system prompt:
    - Cartographer: Returns valid JSON with triples array
    - Critic: Returns pass/fail status with critiques
    - Default: Returns generic mock response
    """
    try:
        body = await request.json()
        messages = body.get("messages", [])
        model = body.get("model", "mock-model")
        
        scenario = _detect_scenario(messages)
        
        if scenario == "cartographer":
            # Return valid extraction JSON
            response_content = {
                "triples": [
                    {
                        "subject": "Mock Vulnerability",
                        "predicate": "MITIGATES",
                        "object": "Mock Mechanism",
                        "confidence": 0.85,
                        "evidence": "This is a mock extraction for testing purposes.",
                    },
                    {
                        "subject": "Mock Mechanism",
                        "predicate": "ENABLES",
                        "object": "Mock Outcome",
                        "confidence": 0.75,
                        "evidence": "Another mock triple for testing.",
                    },
                ],
                "entities": [
                    {"name": "Mock Vulnerability", "type": "Vulnerability"},
                    {"name": "Mock Mechanism", "type": "Mechanism"},
                ],
            }
        elif scenario == "critic":
            # Return validation result
            response_content = {
                "status": "pass",
                "critiques": [],
                "notes": "Mock validation passed",
            }
        else:
            # Default generic response
            response_content = {
                "message": "Mock LLM response",
                "scenario": scenario,
            }
        
        # Format as OpenAI-compatible response
        return JSONResponse({
            "id": "mock-chat-" + str(hash(str(messages))),
            "object": "chat.completion",
            "created": 1234567890,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(response_content, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        })
    except Exception as e:
        # Don't expose exception details to client to prevent information disclosure
        # Log the error server-side for debugging
        logging.error(f"Error in chat completions endpoint: {e}", exc_info=True)
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500,
        )


@app.post("/v1/vision")
async def vision(request: Request) -> JSONResponse:
    """Mock vision endpoint for image analysis.
    
    Returns a dummy vision extraction result.
    """
    try:
        # Parse form data
        form = await request.form()
        payload_str = form.get("payload", "{}")
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        
        # Return mock vision result
        response_content = {
            "caption": "Mock image caption for testing",
            "extracted_facts": [
                {
                    "key": "mock_fact",
                    "value": "42",
                    "unit": "count",
                    "confidence": 0.8,
                }
            ],
            "tables": [],
            "confidence": 0.85,
            "notes": "This is a mock vision extraction result.",
        }
        
        # Format as OpenAI-compatible response
        return JSONResponse({
            "id": "mock-vision-" + str(hash(str(payload))),
            "object": "vision.completion",
            "created": 1234567890,
            "model": payload.get("model", "mock-vision-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(response_content, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 30,
                "total_tokens": 80,
            },
        })
    except Exception as e:
        # Don't expose exception details to client to prevent information disclosure
        # Log the error server-side for debugging
        logging.error(f"Error in vision endpoint: {e}", exc_info=True)
        return JSONResponse(
            {"error": "Internal server error"},
            status_code=500,
        )


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "service": "mock-llm"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MOCK_LLM_PORT", "9000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

