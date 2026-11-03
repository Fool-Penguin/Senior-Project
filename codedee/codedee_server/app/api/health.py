"""
health.py - Health check endpoint verifying backend and Ollama status.
"""

import os
from typing import List
import requests
from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse

from ..models.contracts import HealthCheckResponse

router = APIRouter(tags=["Health"])

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
REQUIRED_MODEL = os.getenv("OLLAMA_REQUIRED_MODEL", "qwen2.5-coder:7b")


@router.get("/health", response_model=HealthCheckResponse)
@router.get("/api/health", response_model=HealthCheckResponse, include_in_schema=False)
def check_health(response: Response):
    """
    Pre-flight health check verifying Ollama reachability and required model availability.
    Returns 200 if healthy, or 503 if Ollama is unreachable or model is missing.
    """
    ollama_url = OLLAMA_BASE_URL.rstrip("/")
    tags_url = f"{ollama_url}/api/tags"

    ollama_reachable = False
    model_available = False
    available_models: List[str] = []

    try:
        res = requests.get(tags_url, timeout=3.0)
        if res.status_code == 200:
            ollama_reachable = True
            data = res.json()
            models_raw = data.get("models", [])
            for m in models_raw:
                name = m.get("name", "")
                if name:
                    available_models.append(name)
                    # Check if matching required model (exact or prefix/tag)
                    if name == REQUIRED_MODEL or name.startswith(f"{REQUIRED_MODEL}:"):
                        model_available = True
    except Exception:
        ollama_reachable = False
        model_available = False

    is_healthy = ollama_reachable and model_available
    health_status = "ok" if is_healthy else ("degraded" if ollama_reachable else "unhealthy")

    result = HealthCheckResponse(
        status=health_status,
        backend_version="1.0.0",
        ollama_reachable=ollama_reachable,
        ollama_url=ollama_url,
        model_available=model_available,
        model_name=REQUIRED_MODEL,
        available_models=available_models,
    )

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return result
