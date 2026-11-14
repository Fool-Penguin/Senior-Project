"""
CodeDEE - Stage 5: FastAPI Localhost IPC Backend Server
Exposes high-speed REST endpoints for the VS Code Extension to trigger:
1. End-to-End Security & Maintainability Audit (/api/v1/analyze)
2. On-Demand Multi-Gate Auto-Repair Patch Generation (/api/v1/request-patches)
3. Health & System Diagnostic Check (/api/v1/health)
"""

from __future__ import annotations

import pathlib
from typing import Optional, Literal
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from codedee.core.pipeline import CodeDEEPipeline, SecurityAuditReport
from codedee.core.parser import CodeDEEParser, SupportedLanguage
from codedee.core.verifier import PatchGenerator, MultiGateVerifier, VerifiedPatch

app = FastAPI(
    title="CodeDEE Security & Quality Analysis Server",
    version="1.0.0",
    description="Local IPC Backend powering the CodeDEE VS Code Extension",
)

# Enable CORS for local VS Code webview communications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Singletons
_pipeline = CodeDEEPipeline(enable_neural_oracle=True)
_patch_generator = PatchGenerator(model_name="qwen2.5-coder:7b")


class AnalyzeRequest(BaseModel):
    code: str = Field(..., description="Source code snippet or full file content")
    language: str = Field(..., description="Programming language ('python', 'javascript', 'typescript')")
    enable_oracle: bool = Field(default=True, description="Enable LLM verification layer")


class PatchRequest(BaseModel):
    code_slice: str = Field(..., description="Vulnerable function code slice")
    language: str = Field(..., description="Programming language ('python', 'javascript', 'typescript')")
    cwe_id: str = Field(..., description="Confirmed CWE ID to fix (from Neuro-Symbolic Reconciliation)")
    source_param: str = Field(default="user_input", description="Symbolic AST tainted input parameter")
    sink_callee: str = Field(default="sink", description="Symbolic AST sensitive execution sink")
    sink_line: int = Field(default=1, description="Symbolic AST sink line number")
    taint_path: list[str] = Field(default_factory=list, description="Symbolic DFG taint path")
    reason: str = Field(default="", description="Neural Oracle contextual flow audit explanation")


class HealthResponse(BaseModel):
    status: str
    engine: str
    supported_languages: list[str]


@app.get("/api/v1/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint to verify backend availability."""
    return HealthResponse(
        status="ONLINE",
        engine="CodeDEE Neuro-Symbolic Engine (Tree-sitter + NetworkX + ChromaDB + Ollama)",
        supported_languages=["python", "javascript", "typescript"],
    )


@app.post("/api/v1/analyze")
def analyze_code(req: AnalyzeRequest):
    """
    Trigger Stage 1 to Stage 3B Analysis Pipeline:
    Returns 8 Maintainability Metrics and Verified Vulnerability findings.
    """
    try:
        lang = CodeDEEParser.normalize_language(req.language)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        pipeline = _pipeline if req.enable_oracle else CodeDEEPipeline(enable_neural_oracle=False)
        report = pipeline.analyze(req.code, lang)
        return asdict(report)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis engine error: {str(e)}",
        )


@app.post("/api/v1/request-patches")
def request_patches(req: PatchRequest):
    """
    Trigger Stage 4 On-Demand Auto-Fix:
    Generates 3-4 patches -> Filters via In-Memory Multi-Gate Verifier ->
    Returns ONLY 100% verified patches for developer diff view.
    """
    try:
        lang = CodeDEEParser.normalize_language(req.language)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        verified_patches = _patch_generator.generate_and_verify(
            code_slice=req.code_slice,
            language=lang,
            cwe_id=req.cwe_id,
            source_param=req.source_param,
            sink_callee=req.sink_callee,
            sink_line=req.sink_line,
            taint_path=req.taint_path,
            neural_reason=req.reason,
        )
        return {
            "cwe_id": req.cwe_id,
            "total_verified": len(verified_patches),
            "patches": [asdict(p) for p in verified_patches],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Patch generation error: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("codedee.server:app", host="127.0.0.1", port=8000, reload=False)
