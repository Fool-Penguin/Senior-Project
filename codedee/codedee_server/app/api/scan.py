"""
scan.py - POST /api/scan endpoint.

Ingests a file, directory, or in-memory code buffer, executes CST parsing,
calculates ISO/IEC 25010 maintainability metrics, runs symbolic taint analysis
for CWE-89 SQL Injection, performs Stage 3B neuro-symbolic audit, and returns
structured findings conforming strictly to the Stage 3B Security Node Output Contract.
"""

import hashlib
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, HTTPException, status
import tree_sitter
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript

from ..maintainability.engine import MaintainabilityEngine
from ..models.contracts import (
    CodeLocation,
    MaintainabilityMetrics,
    NeuroAssessment,
    PipelineMetadata,
    ScanRequest,
    ScanResponse,
    SecurityNodeOutput,
    SymbolicFinding,
    TaintStep,
)
from ..neuro.oracle import NeuralOracle
from ..taint.walker import SymbolicTaintWalker

router = APIRouter(tags=["Scan"])

# Initialize Tree-sitter language grammars
PY_LANGUAGE = tree_sitter.Language(tree_sitter_python.language())
JS_LANGUAGE = tree_sitter.Language(tree_sitter_javascript.language())
TS_LANGUAGE = tree_sitter.Language(tree_sitter_typescript.language_typescript())
TSX_LANGUAGE = tree_sitter.Language(tree_sitter_typescript.language_tsx())

SQL_SINKS_KEYWORDS = [
    "execute",
    "executemany",
    "query",
    "raw",
    "rawQuery",
    "sql_execute",
    "sql_insert",
    "sql_one_row",
]

TAINT_SOURCES_KEYWORDS = [
    "request",
    "req",
    "params",
    "args",
    "query",
    "body",
    "headers",
    "user_input",
    "search",
    "username",
    "password",
    "email",
    "token",
    "id",
]


def detect_language(file_path: str, code_content: Optional[str] = None) -> str:
    """Detect language from file path extension or contents."""
    path_lower = file_path.lower()
    if path_lower.endswith(".py"):
        return "python"
    elif path_lower.endswith((".js", ".mjs", ".cjs")):
        return "javascript"
    elif path_lower.endswith((".ts", ".tsx")):
        return "typescript"

    # Fallback heuristic based on content
    if code_content:
        if "def " in code_content or ("import " in code_content and ":" in code_content):
            return "python"
        elif "const " in code_content or "function " in code_content or "let " in code_content:
            if ": string" in code_content or ": number" in code_content or "interface " in code_content:
                return "typescript"
            return "javascript"

    return "python"


def get_parser_for_language(lang: str, is_tsx: bool = False) -> tree_sitter.Parser:
    """Create a Tree-sitter Parser for target language."""
    if lang == "python":
        return tree_sitter.Parser(PY_LANGUAGE)
    elif lang == "javascript":
        return tree_sitter.Parser(JS_LANGUAGE)
    elif lang == "typescript":
        return tree_sitter.Parser(TSX_LANGUAGE if is_tsx else TS_LANGUAGE)
    return tree_sitter.Parser(PY_LANGUAGE)


def compute_maintainability_metrics(
    code: str, lang: str, tree: Optional[tree_sitter.Tree] = None
) -> MaintainabilityMetrics:
    """
    Compute exactly 8 metrics under ISO/IEC 25010 delegating to MaintainabilityEngine.
    """
    engine = MaintainabilityEngine()
    return engine.analyze_code(code, lang)


def extract_cwe89_vulnerabilities(
    file_path: str,
    code: str,
    lang: str,
    tree: Optional[tree_sitter.Tree] = None,
    metrics: Optional[MaintainabilityMetrics] = None,
) -> List[SecurityNodeOutput]:
    """
    Symbolic analysis traversing AST and DFG to identify SQL injection taint paths:
    Taint Source -> Intermediate DFG steps -> SQL Sink, followed by Stage 3B Neural Oracle review.
    """
    if metrics is None:
        engine = MaintainabilityEngine()
        metrics = engine.analyze_code(code, lang, file_path=file_path)

    taint_walker = SymbolicTaintWalker()
    findings = taint_walker.analyze_code(code=code, language=lang, file_path=file_path)

    active_flaws = [f for f in findings if not f.sanitized]
    if not active_flaws:
        return []

    # Deduplicate multiple DFG paths reaching the same sink location
    seen_sinks: Set[Tuple[Any, ...]] = set()
    unique_flaws: List[SymbolicFinding] = []
    for f in active_flaws:
        snk = f.sink_node if isinstance(f.sink_node, dict) else f.sink_node.model_dump()
        snk_key = (snk.get("file"), snk.get("line"), snk.get("symbol"))
        if snk_key not in seen_sinks:
            seen_sinks.add(snk_key)
            unique_flaws.append(f)

    oracle = NeuralOracle()
    issues: List[SecurityNodeOutput] = []

    for flaw in unique_flaws:
        snk = flaw.sink_node if isinstance(flaw.sink_node, dict) else flaw.sink_node.model_dump()
        snk_line = snk.get("line", 1)
        snk_expr = snk.get("expression", "")

        # Unique deterministic issue_id
        raw_hash_seed = f"{file_path}:{snk_line}:CWE-89:{snk_expr}"
        issue_hash = hashlib.sha256(raw_hash_seed.encode("utf-8")).hexdigest()[:10]
        issue_id = f"ISSUE-CWE89-{issue_hash}"

        # Normalize severity to canonical HIGH for CWE-89
        flaw.severity = "HIGH"

        # Reconcile file paths to requested file_path
        if isinstance(flaw.source_node, dict):
            flaw.source_node["file"] = file_path
        if isinstance(flaw.sink_node, dict):
            flaw.sink_node["file"] = file_path
        for step in (flaw.taint_path or []):
            if isinstance(step, dict):
                step["file"] = file_path

        # Contextual review via Neural Oracle (Program Slicer + ChromaDB RAG)
        neuro_assessment = oracle.assess_finding(finding=flaw, file_content=code, language=lang)



        pipeline_metadata = PipelineMetadata(
            scan_timestamp=datetime.now(timezone.utc).isoformat(),
            file_path=file_path,
            language=lang,
            maintainability_metrics=metrics.to_summary_dict(),
            execution_time_ms=0.0,
            stage="Stage 3B - Neuro-Symbolic Audit",
            model_name="qwen2.5-coder:7b",
        )

        issue = SecurityNodeOutput(
            issue_id=issue_id,
            target_file=file_path,
            symbolic_finding=flaw,
            neuro_assessment=neuro_assessment,
            pipeline_metadata=pipeline_metadata,
        )
        issues.append(issue)

    return issues


@router.post("/api/scan", response_model=ScanResponse)
def scan_code(req: ScanRequest) -> ScanResponse:
    """
    Scan a file, directory, or active editor buffer for CWE-89 SQL Injection.
    Executes CST parsing, ISO/IEC 25010 maintainability analysis, and Stage 3B audit.
    """
    start_time = time.time()
    all_issues: List[SecurityNodeOutput] = []
    files_scanned = 0
    maintainability_summary: Dict[str, Any] = {}
    engine = MaintainabilityEngine()

    # Case 1: In-memory code content scan
    if req.code_content is not None:
        virtual_path = req.file_name or req.target_path or "active_editor.py"
        lang = req.language or detect_language(virtual_path, req.code_content)

        metrics = engine.analyze_code(req.code_content, lang, file_path=virtual_path)
        maintainability_summary = metrics.to_summary_dict()
        file_issues = extract_cwe89_vulnerabilities(virtual_path, req.code_content, lang, metrics=metrics)
        all_issues.extend(file_issues)
        files_scanned = 1

    # Case 2: Target path scan
    elif req.target_path is not None:
        target = Path(req.target_path)
        if not target.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target path not found: {req.target_path}",
            )

        target_files: List[Path] = []
        if target.is_file():
            target_files.append(target)
        elif target.is_dir():
            for root, dirs, files in os.walk(target):
                # Filter out build/ignore dirs
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv", "venv", "dist")]
                for f in files:
                    if f.endswith((".py", ".js", ".mjs", ".ts", ".tsx")):
                        target_files.append(Path(root) / f)

        for tf in target_files:
            try:
                content = tf.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lang = req.language or detect_language(str(tf), content)
            metrics = engine.analyze_code(content, lang, file_path=str(tf))
            maintainability_summary = metrics.to_summary_dict()
            file_issues = extract_cwe89_vulnerabilities(str(tf), content, lang, metrics=metrics)
            all_issues.extend(file_issues)
            files_scanned += 1
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either target_path or code_content must be provided.",
        )

    duration_ms = round((time.time() - start_time) * 1000, 2)
    for issue in all_issues:
        issue.pipeline_metadata.execution_time_ms = duration_ms

    return ScanResponse(
        status="completed",
        target_path=req.target_path or req.file_name or "active_editor.py",
        files_scanned=files_scanned,
        issues_count=len(all_issues),
        issues=all_issues,
        maintainability=maintainability_summary,
        execution_time_ms=duration_ms,
    )
