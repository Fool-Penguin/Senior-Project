"""
main.py - CodeDEE Backend Server Application Entrypoint.

Provides FastAPI ASGI application with CORS middleware, lifespan events,
and modular routers:
- GET /health: Ollama and model pre-flight check
- POST /api/scan: Full static analysis and neuro-symbolic audit
- POST /api/generate-patches: In-memory multi-gate verified patch generation
- POST /api/apply-patch: Safe disk patch application with backup
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import apply, health, patches, scan

app = FastAPI(
    title="CodeDEE Backend Server",
    description="Continuous Code Quality & Automated Security Program Repair System",
    version="1.0.0",
)

# Configure CORS for VS Code Extension and local frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register modular API routers
app.include_router(health.router)
app.include_router(scan.router)
app.include_router(patches.router)
app.include_router(apply.router)


@app.get("/")
def root():
    """Server metadata and endpoint directory."""
    return {
        "name": "CodeDEE Backend Server",
        "version": "1.0.0",
        "status": "online",
        "endpoints": {
            "health": "/health",
            "scan": "/api/scan",
            "generate_patches": "/api/generate-patches",
            "apply_patch": "/api/apply-patch",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
