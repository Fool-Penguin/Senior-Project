"""
contracts.py - Stage 3B Security Node Output Contract and CodeDEE API Models.

Defines strict Pydantic schemas governing:
1. Stage 3B Security Node Output Contract:
   - issue_id
   - target_file
   - symbolic_finding
   - neuro_assessment
   - pipeline_metadata
2. Maintainability Metrics (ISO/IEC 25010 8 metrics)
3. Multi-Gate Verification Results
4. REST API Requests and Responses:
   - GET /health
   - POST /api/scan
   - POST /api/generate-patches
   - POST /api/apply-patch
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


# ============================================================================
# 1. Maintainability & Code Location Primitives
# ============================================================================

class CodeLocation(BaseModel):
    """Pinpoints source or sink code locations."""
    file: str = Field(..., description="File path relative to repository or absolute")
    line: int = Field(..., ge=1, description="1-indexed line number")
    column: Optional[int] = Field(None, ge=0, description="0-indexed column offset")
    symbol: str = Field("", description="Variable or identifier name")
    expression: Optional[str] = Field(None, description="Expression text")
    code_statement: Optional[str] = Field(None, description="Enclosing statement string")


class TaintStep(BaseModel):
    """Step in a taint propagation path."""
    step_index: int = Field(..., ge=1, description="1-indexed step in sequence")
    file: str = Field(..., description="File where propagation occurs")
    line: int = Field(..., ge=1, description="Line number of propagation")
    symbol: str = Field(..., description="Tainted variable or symbol")
    operation: str = Field("propagation", description="Type: source, assignment, call_arg, sink")
    code_snippet: Optional[str] = Field(None, description="Line snippet")


class MaintainabilityMetrics(BaseModel):
    """
    ISO/IEC 25010 Maintainability Engine (Exactly 8 metrics).
    Excludes SQALE, LCOM4, DIT, NOM, Raw LOC, Nesting Depth.
    """
    # Function-level (4 metrics)
    cyclomatic_complexity: int = Field(1, ge=1, description="McCabe Cyclomatic Complexity (CC)")
    cognitive_complexity: int = Field(0, ge=0, description="SonarQube Cognitive Complexity")
    parameter_count: int = Field(0, ge=0, description="Number of formal parameters")
    function_sloc: int = Field(1, ge=1, description="Function source lines of code")

    # File-level (4 metrics)
    file_sloc: int = Field(1, ge=1, description="Total file source lines of code")
    module_coupling_ce: int = Field(0, ge=0, description="Efferent Coupling (Ce)")
    module_coupling_ca: int = Field(0, ge=0, description="Afferent Coupling (Ca)")
    duplicated_blocks: int = Field(0, ge=0, description="Count of duplicate blocks")
    comment_density: float = Field(0.0, ge=0.0, le=1.0, description="Comment lines / total lines ratio")

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert metrics to nested ISO/IEC 25010 summary."""
        instability = 0.0
        total_c = self.module_coupling_ce + self.module_coupling_ca
        if total_c > 0:
            instability = round(self.module_coupling_ce / total_c, 3)

        return {
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "cognitive_complexity": self.cognitive_complexity,
            "parameter_count": self.parameter_count,
            "function_sloc": self.function_sloc,
            "file_sloc": self.file_sloc,
            "module_coupling": {
                "Ce": self.module_coupling_ce,
                "Ca": self.module_coupling_ca,
                "instability": instability,
            },
            "duplicated_blocks": self.duplicated_blocks,
            "comment_density": self.comment_density,
        }


# ============================================================================
# 2. Stage 3B Security Node Output Contract
# ============================================================================

class SymbolicFinding(BaseModel):
    """
    Symbolic analysis result from Stage 3A.
    """
    cwe_id: str = Field("CWE-89", description="CWE identifier")
    cwe_name: str = Field(
        "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')",
        description="Canonical CWE name",
    )
    severity: str = Field("HIGH", description="Severity: CRITICAL, HIGH, MEDIUM, LOW")
    source_node: Dict[str, Any] = Field(default_factory=dict, description="Taint source node {file, line, symbol, expression}")
    sink_node: Dict[str, Any] = Field(default_factory=dict, description="Taint sink node {file, line, symbol, expression}")
    taint_path: List[Dict[str, Any]] = Field(default_factory=list, description="Ordered steps from source to sink")
    sanitized: bool = Field(False, description="Whether taint is sanitized")
    symbolic_confidence: float = Field(1.0, ge=0.0, le=1.0, description="Deterministic confidence score")
    code_slice: Optional[str] = Field(None, description="Extracted enclosing function/method code slice")

    @model_validator(mode="before")
    @classmethod
    def reconcile_nodes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If 'source' was provided instead of 'source_node'
            if "source" in data and not data.get("source_node"):
                src = data["source"]
                data["source_node"] = src if isinstance(src, dict) else src.model_dump()
            # If 'sink' was provided instead of 'sink_node'
            if "sink" in data and not data.get("sink_node"):
                snk = data["sink"]
                data["sink_node"] = snk if isinstance(snk, dict) else snk.model_dump()
        return data


class NeuroAssessment(BaseModel):
    """
    Neural Oracle assessment result from Stage 3B.
    """
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 - 1.0)")
    risk_level: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW, SAFE")
    sanitizer_detected: bool = Field(..., description="Whether a valid sanitizer was detected")
    sanitizer_details: Optional[str] = Field(None, description="Sanitizer pattern or mechanism")
    is_false_positive: bool = Field(False, description="Flagged as false positive")
    reasoning: str = Field(..., description="AI chain-of-thought rationale")
    flagged_for_review: bool = Field(False, description="Flagged for manual inspection without hard deletion")
    suggested_remediation: Optional[str] = Field(None, description="Suggested remediation text")


class PipelineMetadata(BaseModel):
    """
    Metadata capturing environment, timing, and maintainability metrics.
    """
    scan_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    file_path: str = Field(..., description="Analyzed file path")
    language: str = Field("python", description="Language of target file")
    maintainability_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="8 ISO/IEC 25010 metrics dictionary",
    )
    execution_time_ms: float = Field(0.0, ge=0.0, description="Pipeline latency in ms")
    stage: str = Field("Stage 3B - Neuro-Symbolic Audit", description="Execution stage identifier")
    model_name: str = Field("qwen2.5-coder:7b", description="LLM model identifier")

    @model_validator(mode="before")
    @classmethod
    def reconcile_maintainability(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "maintainability" in data and not data.get("maintainability_metrics"):
                m = data["maintainability"]
                data["maintainability_metrics"] = m if isinstance(m, dict) else m.model_dump()
        return data


class SecurityNodeOutput(BaseModel):
    """
    Stage 3B Security Node Output Contract.
    Mandatory fields: issue_id, target_file, symbolic_finding, neuro_assessment, pipeline_metadata.
    """
    issue_id: str = Field(..., description="Unique issue hash (e.g. CWE89-filename-line)")
    target_file: str = Field(..., description="Path to file containing issue")
    symbolic_finding: SymbolicFinding = Field(..., description="Stage 3A symbolic finding")
    neuro_assessment: Optional[NeuroAssessment] = Field(None, description="Stage 3B neural assessment")
    pipeline_metadata: PipelineMetadata = Field(..., description="Pipeline execution metadata")


# Alias for backward/forward compatibility
Stage3BSecurityNodeOutput = SecurityNodeOutput


# ============================================================================
# 3. Multi-Gate Verification Models
# ============================================================================

class GateResult(BaseModel):
    """Result of an individual verification gate."""
    passed: bool = Field(..., description="Gate pass/fail boolean")
    details: str = Field("", description="Gate verification details or diagnostic")


class GateVerificationResult(BaseModel):
    """
    Multi-Gate Verification Contract result conforming to PROJECT.md § 4.
    """
    gate_1_syntax: bool = Field(..., description="Gate 1: Tree-sitter CST syntax validity")
    gate_2_interface: bool = Field(..., description="Gate 2: Function name, arity, and parameter names preserved")
    gate_3_neutralization: bool = Field(..., description="Gate 3: Taint sink neutralization (no concatenation/interpolation, parameter placeholders used)")
    gate_4_maintainability: bool = Field(..., description="Gate 4: Maintainability non-regression (delta CC <= 0)")
    gate_6_sast_rescan: bool = Field(..., description="Gate 6: SAST re-scan clean (0 active flaws)")
    is_100_percent_verified: bool = Field(..., description="True if and only if Gates 1, 2, 3, 4, 6 ALL pass")
    delta_cc: int = Field(0, description="Delta Cyclomatic Complexity")
    passed_gates: List[str] = Field(default_factory=list, description="Names of passed gates")
    gate_details: Dict[str, str] = Field(default_factory=dict, description="Detailed diagnostic per gate")



class VerifiedPatch(BaseModel):
    """A candidate patch that has passed in-memory Multi-Gate verification."""
    patch_id: str = Field(..., description="Unique patch identifier")
    diff: str = Field(..., description="Unified diff formatted for VS Code diff viewer")
    remediated_code: str = Field(..., description="Full remediated code")
    passed_gates: List[str] = Field(
        default_factory=lambda: ["Gate 1", "Gate 2", "Gate 3", "Gate 4", "Gate 6"],
        description="List of gates passed (all required for 100% verified)",
    )
    delta_cc: int = Field(0, description="Delta Cyclomatic Complexity (must be <= 0)")
    explanation: Optional[str] = Field(None, description="AI rationale explaining remediation")
    gate1_syntax: Optional[GateResult] = Field(None, description="Gate 1 CST syntax validity")
    gate2_interface: Optional[GateResult] = Field(None, description="Gate 2 interface preservation")
    gate3_taint_neutralized: Optional[GateResult] = Field(None, description="Gate 3 sink neutralization")
    gate4_maintainability: Optional[GateResult] = Field(None, description="Gate 4 maintainability non-regression")
    gate6_sast_rescan: Optional[GateResult] = Field(None, description="Gate 6 SAST re-scan")


# ============================================================================
# 4. REST API Request / Response Models
# ============================================================================

# GET /health
class HealthCheckResponse(BaseModel):
    status: str = Field("ok", description="Overall health: ok, healthy, degraded, unhealthy")
    backend_version: str = Field("1.0.0", description="Backend server version")
    ollama_reachable: bool = Field(..., description="Ollama daemon reachability")
    ollama_url: str = Field("http://127.0.0.1:11434", description="Ollama API base URL")
    model_available: bool = Field(..., description="Whether required model is available")
    model_name: str = Field("qwen2.5-coder:7b", description="Required model name")
    available_models: List[str] = Field(default_factory=list, description="Models installed in Ollama")


# POST /api/scan
class ScanRequest(BaseModel):
    target_path: Optional[str] = Field(None, description="Absolute or relative path to file or folder on disk")
    code_content: Optional[str] = Field(None, description="In-memory code content buffer (e.g., active editor)")
    file_name: Optional[str] = Field("active_editor.py", description="Virtual file name for in-memory code")
    language: Optional[str] = Field(None, description="Language: python, javascript, typescript (auto-detected if omitted)")


class ScanResponse(BaseModel):
    status: str = Field("completed", description="Scan execution status")
    target_path: Optional[str] = Field(None, description="Target path scanned")
    files_scanned: int = Field(0, ge=0, description="Number of files scanned")
    issues_count: int = Field(0, ge=0, description="Number of issues found")
    issues: List[SecurityNodeOutput] = Field(default_factory=list, description="Conforming Stage 3B findings")
    maintainability: Optional[Dict[str, Any]] = Field(None, description="Aggregate maintainability metrics")
    execution_time_ms: float = Field(0.0, ge=0.0, description="Scan execution time in ms")


# POST /api/generate-patches
class GeneratePatchesRequest(BaseModel):
    issue_id: str = Field(..., description="Issue identifier returned by /api/scan")
    target_file: Optional[str] = Field(None, description="Path to target file on disk")
    candidate_count: int = Field(3, ge=1, le=5, description="Number of candidate fixes to generate (3-4)")
    num_candidates: Optional[int] = Field(None, ge=1, le=5, description="Alias for candidate_count")
    code_content: Optional[str] = Field(None, description="Optional raw code if not reading from disk")

    @model_validator(mode="before")
    @classmethod
    def reconcile_candidates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "num_candidates" in data and data["num_candidates"] is not None:
                data["candidate_count"] = data["num_candidates"]
        return data


class GeneratePatchesResponse(BaseModel):
    issue_id: str = Field(..., description="Issue identifier")
    target_file: str = Field(..., description="Target file path")
    total_generated: int = Field(0, ge=0, description="Total candidate patches generated")
    verified_count: int = Field(0, ge=0, description="Count of 100% verified patches")
    pruned_count: int = Field(0, ge=0, description="Count of rejected candidate patches")
    verified_patches: List[VerifiedPatch] = Field(default_factory=list, description="Verified patch list")


# POST /api/apply-patch
class ApplyPatchRequest(BaseModel):
    target_file: str = Field(..., description="Path to target file on disk")
    patch_diff: Optional[str] = Field(None, description="Unified patch diff to apply")
    diff: Optional[str] = Field(None, description="Alias for patch_diff")
    remediated_code: Optional[str] = Field(None, description="Remediated code to substitute directly")
    patch_code: Optional[str] = Field(None, description="Alias for remediated_code")
    patch_id: Optional[str] = Field(None, description="ID of patch being applied")

    @model_validator(mode="before")
    @classmethod
    def reconcile_patch_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("patch_diff") and data.get("diff"):
                data["patch_diff"] = data["diff"]
            if not data.get("remediated_code") and data.get("patch_code"):
                data["remediated_code"] = data["patch_code"]
        return data


class ApplyPatchResponse(BaseModel):
    success: bool = Field(..., description="True if patch application succeeded")
    target_file: str = Field(..., description="Target file path")
    backup_file: Optional[str] = Field(None, description="Path to safety backup file (.bak)")
    message: str = Field(..., description="Execution outcome message")
    updated_content: Optional[str] = Field(None, description="Updated file content after patch")
