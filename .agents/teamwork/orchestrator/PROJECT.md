# Project: CodeDEE — Continuous Code Quality & Automated Security Program Repair System

## Architecture
CodeDEE is an end-to-end continuous code quality and automated security program repair system with a vertical slice prototype focusing on SQL Injection (CWE-89) across Python, JavaScript, and TypeScript.
The system is architected as a monorepo consisting of:
1. `codedee_server/`: A high-performance FastAPI backend hosting:
   - **Stage 1 & 2 CST & Graph Modeling**: Tree-sitter AST parsing, NetworkX Call Graph (inter-procedural / cross-file), Control-Flow Graph (CFG), and Data-Flow Graph (DFG).
   - **Maintainability Engine**: ISO/IEC 25010 compliant calculator computing exactly 8 metrics (CC, Cognitive Complexity, Parameter Count, Function SLOC, File SLOC, Module Coupling Ce/Ca, Duplicated Blocks, Comment Density).
   - **Stage 3A Symbolic Taint Walker**: Forward/backward traversal on DFG tracking tainted input from sources (e.g. `request.args`, `req.query`, `params`) to SQL sinks (e.g. `cursor.execute`, `db.query`, `client.query`).
   - **Stage 3B Neuro-Symbolic Audit**: CST Program Slicer + ChromaDB RAG Knowledge Base (`mini_test_knowledges.json`) + Neural Oracle querying local Ollama `qwen2.5-coder:7b` for confidence assessment.
   - **Stage 4 In-Memory Multi-Gate Verifier**: Validating 3–4 generated candidate patches across Gate 1 (CST syntax check), Gate 2 (Interface preservation), Gate 3 (Taint sink neutralization), Gate 4 (Maintainability non-regression: delta CC <= 0), and Gate 6 (SAST re-scan: 0 new flaws).
2. `codedee_extension/`: A modern VS Code extension providing:
   - Command `CodeDEE: Scan Current File / Project`.
   - Rich interactive Webview Panel visualizing detected CWE-89 flaws, taint flow (Source -> Steps -> Sink), maintainability metrics, and AI explanations.
   - Diff viewer using VS Code native `vscode.diff` provider and one-click patch application invoking `/api/apply-patch`.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Monorepo Scaffolding & Requirements | Scaffold `codedee_server/` structure and `requirements.txt` with FastAPI, Tree-sitter, NetworkX, ChromaDB, etc. | M1 | ORIGINAL_REQUEST §R1 |
| F2 | CWE-89 Dataset Extraction | Extract `codedee_server/data/mini_test_datasets.json` with 105 samples and 14 exact columns from master catalogue | M1 | ORIGINAL_REQUEST §R1 |
| F3 | Stage 3B Pydantic Contract Models | Define strict Pydantic schemas for `issue_id`, `target_file`, `symbolic_finding`, `neuro_assessment`, `pipeline_metadata` | M1 | ORIGINAL_REQUEST §R1 |
| F4 | Pre-flight Health Check Endpoint | `GET /health` verifying Ollama reachability and `qwen2.5-coder:7b` availability | M1 | ORIGINAL_REQUEST §R1 |
| F5 | Full Scan API Endpoint | `POST /api/scan` ingesting file/folder, running Stages 1–3, and returning Stage 3B contract outputs | M1 | ORIGINAL_REQUEST §R1 |
| F6 | Patch Generation API Endpoint | `POST /api/generate-patches` taking `issue_id`, querying Ollama, running Multi-Gate verification, returning verified patches | M1 | ORIGINAL_REQUEST §R1 |
| F7 | Patch Application API Endpoint | `POST /api/apply-patch` applying diff directly to target source file | M1 | ORIGINAL_REQUEST §R1 |
| F8 | Multi-Language CST Parsing | Concrete Syntax Tree parsing for Python, JavaScript, and TypeScript via modular Tree-sitter 0.26 packages | M2 | ORIGINAL_REQUEST §R2 |
| F9 | NetworkX Call Graph Builder | Inter-procedural and cross-file function call graph with import resolution | M2 | ORIGINAL_REQUEST §R2 |
| F10 | NetworkX CFG Builder | Control-Flow Graph modeling branching statements (`if`, `for`, `while`, `try-catch`) | M2 | ORIGINAL_REQUEST §R2 |
| F11 | NetworkX DFG Builder | Data-Flow Graph modeling Def-Use chains, parameter bindings, and variable propagation | M2 | ORIGINAL_REQUEST §R2 |
| F12 | ISO/IEC 25010 Maintainability Engine | Computing exactly 8 metrics: CC, Cognitive Complexity, Params, Func SLOC, File SLOC, Ce/Ca, Duplications, Comment Density | M2 | ORIGINAL_REQUEST §R2 |
| F13 | Symbolic Taint Walker | DFG traversal from HTTP/CLI sources to SQL sinks detecting unparameterized concatenation | M2 | ORIGINAL_REQUEST §R2 |
| F14 | ChromaDB Knowledge Base Seeding | Seed `mini_test_knowledges.json` into ChromaDB collection with CWE-89 descriptions, patterns, and sanitizers | M3 | ORIGINAL_REQUEST §R3 |
| F15 | CST Program Slicer | Full function/method extraction for complete source and sink context | M3 | ORIGINAL_REQUEST §R3 |
| F16 | Neural Oracle (Stage 3B Assessment) | Querying local Ollama `qwen2.5-coder:7b` with code slice and RAG context returning structured JSON assessment | M3 | ORIGINAL_REQUEST §R3 |
| F17 | Neural Oracle (Stage 4 Patch Generation) | Generating 3–4 candidate fixes via Ollama `qwen2.5-coder:7b` | M3 | ORIGINAL_REQUEST §R3 |
| F18 | In-Memory Multi-Gate Verifier | Executing Gates 1, 2, 3, 4, 6 and retaining only 100% verified patches | M3 | ORIGINAL_REQUEST §R3 |
| F19 | VS Code Extension Scaffolding | Scaffold `codedee_extension/` with `package.json`, `tsconfig.json`, and dependencies | M4 | ORIGINAL_REQUEST §R4 |
| F20 | Extension Configuration & Scan Command | Server URL setting (`http://127.0.0.1:8000`) and `CodeDEE: Scan Current File / Project` command | M4 | ORIGINAL_REQUEST §R4 |
| F21 | Interactive Webview Panel | Displaying CWE-89 issues, taint paths, risk levels, AI reasoning, and `[Request AI Patches]` button | M4 | ORIGINAL_REQUEST §R4 |
| F22 | Diff Viewer & Patch Application | `vscode.diff` provider for candidate patches and `[Apply Patch]` button invoking `/api/apply-patch` | M4 | ORIGINAL_REQUEST §R4 |
| F23 | E2E Testing Suite & Integration Verification | Opaque-box E2E test suite (Tiers 1–4) + End-to-end integration test against Python and JS CWE-89 samples | M5 | ORIGINAL_REQUEST §Acceptance Criteria |
| F24 | Adversarial Coverage Hardening (Tier 5) | White-box stress testing and boundary condition verification | M5 | Project Pattern §Phase 2 |

---

## Milestones
| # | Name | Scope / Features | Dependencies | Status |
|---|------|------------------|-------------|--------|
| M1 | Monorepo Scaffolding & Backend Architecture | F1, F2, F3, F4, F5, F6, F7 | None | DONE |
| M2 | Static Analysis & Graph Modeling Engine | F8, F9, F10, F11, F12, F13 | M1 (contracts) | DONE |
| M3 | Neuro-Symbolic Audit & In-Memory Multi-Gate Verifier | F14, F15, F16, F17, F18 | M1, M2 | IN_PROGRESS |
| M4 | VS Code Extension | F19, F20, F21, F22 | M1 (API contracts) | PLANNED |
| M5 | Final Milestone: E2E Integration & Adversarial Hardening | F23, F24 | M1, M2, M3, M4 | PLANNED |

---

## Interface Contracts

### 1. Stage 3B Security Node Output Contract (`codedee_server/app/models/contracts.py`)
```python
class SymbolicFinding(BaseModel):
    cwe_id: str = "CWE-89"
    cwe_name: str = "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')"
    severity: str
    source_node: Dict[str, Any]      # {file, line, column, symbol, expression}
    sink_node: Dict[str, Any]        # {file, line, column, symbol, expression}
    taint_path: List[Dict[str, Any]] # Ordered steps from source to sink
    sanitized: bool = False

class NeuroAssessment(BaseModel):
    confidence_score: float          # 0.0 - 1.0
    risk_level: str                  # HIGH, MEDIUM, LOW, SAFE
    sanitizer_detected: bool
    sanitizer_details: Optional[str] = None
    is_false_positive: bool = False
    reasoning: str

class PipelineMetadata(BaseModel):
    scan_timestamp: str
    file_path: str
    language: str
    maintainability_metrics: Dict[str, Any] # 8 ISO/IEC 25010 metrics

class SecurityNodeOutput(BaseModel):
    issue_id: str                    # Unique hash (e.g., cwe_id + file + line)
    target_file: str
    symbolic_finding: SymbolicFinding
    neuro_assessment: Optional[NeuroAssessment] = None
    pipeline_metadata: PipelineMetadata
```

### 2. REST API Endpoints Contract
- `GET /health` -> `{"status": "ok", "ollama_reachable": true, "model_available": true, "model_name": "qwen2.5-coder:7b"}`
- `POST /api/scan`:
  - Request: `{"target_path": str}`
  - Response: `{"target_path": str, "issues_count": int, "issues": List[SecurityNodeOutput], "maintainability": Dict[str, Any]}`
- `POST /api/generate-patches`:
  - Request: `{"issue_id": str, "target_file": str, "candidate_count": int = 3}`
  - Response: `{"issue_id": str, "target_file": str, "verified_patches": List[VerifiedPatch]}`
  - Each `VerifiedPatch` contains: `patch_id`, `diff`, `remediated_code`, `passed_gates: ["Gate 1", "Gate 2", "Gate 3", "Gate 4", "Gate 6"]`, `delta_cc: int`
- `POST /api/apply-patch`:
  - Request: `{"target_file": str, "patch_diff": str, "remediated_code": Optional[str] = None}`
  - Response: `{"success": bool, "target_file": str, "message": str}`

### 3. Maintainability Engine Contract (Exactly 8 Metrics)
- Function-level:
  1. `cyclomatic_complexity`: int (McCabe metric)
  2. `cognitive_complexity`: int (SonarQube specification)
  3. `parameter_count`: int
  4. `function_sloc`: int (Source lines of code, excluding comments & blanks)
- File-level:
  5. `file_sloc`: int
  6. `module_coupling`: `{"Ce": int, "Ca": int, "instability": float}`
  7. `duplicated_blocks`: int
  8. `comment_density`: float (comment_lines / total_lines)

### 4. Multi-Gate Verifier Contract
- `verify_patch(original_code: str, patched_code: str, language: str) -> GateVerificationResult`:
  - `gate_1_syntax`: bool (Tree-sitter CST has no ERROR or MISSING nodes)
  - `gate_2_interface`: bool (Function name and arity/parameter names preserved)
  - `gate_3_neutralization`: bool (SQL sink has no string formatting/concatenation; uses parameterized placeholders)
  - `gate_4_maintainability`: bool (delta CC <= 0)
  - `gate_6_sast_rescan`: bool (0 new flaws, taint path eliminated)
  - `is_100_percent_verified`: bool (gate_1 and gate_2 and gate_3 and gate_4 and gate_6)

---

## Code Layout
`d:\4th-year\Senior-Project\codedee\`
```
codedee/
├── codedee_server/
│   ├── requirements.txt
│   ├── data/
│   │   ├── mini_test_datasets.json
│   │   └── mini_test_knowledges.json
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── contracts.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── scan.py
│   │   │   ├── patches.py
│   │   │   └── apply.py
│   │   ├── parser/
│   │   │   ├── __init__.py
│   │   │   └── cst_manager.py
│   │   ├── graphs/
│   │   │   ├── __init__.py
│   │   │   ├── call_graph.py
│   │   │   ├── cfg.py
│   │   │   └── dfg.py
│   │   ├── maintainability/
│   │   │   ├── __init__.py
│   │   │   └── engine.py
│   │   ├── taint/
│   │   │   ├── __init__.py
│   │   │   └── walker.py
│   │   ├── neuro/
│   │   │   ├── __init__.py
│   │   │   ├── rag.py
│   │   │   ├── slicer.py
│   │   │   └── oracle.py
│   │   └── verifier/
│   │       ├── __init__.py
│   │       └── multi_gate.py
│   ├── scripts/
│   │   ├── extract_dataset.py
│   │   └── seed_knowledge.py
│   └── tests/
│       ├── __init__.py
│       ├── test_dataset.py
│       ├── test_treesitter_graphs.py
│       ├── test_maintainability.py
│       ├── test_taint_walker.py
│       ├── test_multi_gate.py
│       ├── test_api.py
│       └── test_e2e_integration.py
└── codedee_extension/
    ├── package.json
    ├── tsconfig.json
    ├── src/
    │   ├── extension.ts
    │   ├── apiClient.ts
    │   ├── diffProvider.ts
    │   └── webviewPanel.ts
    └── media/
        ├── panel.css
        └── panel.js
```
