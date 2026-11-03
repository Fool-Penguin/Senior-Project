Build CodeDEE, an end-to-end continuous code quality and automated security program repair system, with a vertical slice prototype focusing on SQL Injection (CWE-89) across Python, JavaScript, and TypeScript.
Execute with the requested team: Agent 1 (Backend System Architect & API Lead), Agent 2 (Static Analysis & Graph Engineer), Agent 3 (Neuro-Symbolic & Verifier Engineer), Agent 4 (VS Code Extension Engineer).

Working directory: d:\4th-year\Senior-Project\codedee
Integrity mode: development

## Verification Resources
- Source dataset catalogue: `D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json`

## Requirements

### R1. Monorepo Scaffolding & Backend Architecture (`codedee_server/`)
Scaffold `codedee_server/` with `requirements.txt` containing `fastapi`, `uvicorn`, `pydantic`, `tree-sitter`, `tree-sitter-languages`, `networkx`, `chromadb`, `requests`, and `pytest`. Implement strict Pydantic schemas for the Stage 3B Security Node Output Contract (`issue_id`, `target_file`, `symbolic_finding`, `neuro_assessment`, `pipeline_metadata`). Create the following REST API endpoints:
- `GET /health`: Pre-flight check verifying Ollama reachability and `qwen2.5-coder:7b` model availability.
- `POST /api/scan`: Ingests a file or folder, executes Stages 1–3, and returns structured findings.
- `POST /api/generate-patches`: Takes an `issue_id`, generates 3–4 candidate fixes via Ollama `qwen2.5-coder:7b`, runs in-memory Multi-Gate verification, and returns only 100% verified patches.
- `POST /api/apply-patch`: Applies the selected patch diff directly to the target file.
Extract `codedee_server/data/mini_test_datasets.json` from `D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json` filtered for `cwe_id == 'CWE-89'` containing the exact 14 columns: `sample_id`, `language`, `Is_vulnerable`, `cwe_id`, `cwe_name`, `cwe_description`, `owasp_category`, `cvss_v31_vector`, `sources`, `source_pattern`, `sink_pattern`, `sanitizer_pattern`, `original_code`, `fixed_code`.

### R2. Static Analysis & Graph Modeling Engine (Stages 1, 2, 3A, 3B)
Implement Concrete Syntax Tree (CST) parsing using Tree-sitter for Python, JavaScript, and TypeScript. Build the following graphs using NetworkX:
- Call Graph: Inter-procedural and cross-file function calls.
- Control-Flow Graph (CFG): Branching statements (`if`, `for`, `while`, `try-catch`).
- Data-Flow Graph (DFG): Definition-Use chains and variable propagation.
Implement the Maintainability Engine under ISO/IEC 25010 calculating exactly 8 metrics (no SQALE, explicitly excluding LCOM4, DIT, NOM, Raw LOC, and Nesting Depth):
- Function-level: (1) Cyclomatic Complexity (CC), (2) Cognitive Complexity, (3) Parameter Count, (4) Function SLOC.
- File-level: (5) File SLOC, (6) Module Coupling (Ce / Ca), (7) Duplicated Blocks, (8) Comment Density.
Implement the Symbolic Taint Walker traversing the DFG from taint sources (e.g. `request.args`, `req.query`, `params`) to SQL sinks (e.g. `cursor.execute`, `db.query`, `client.query`).

### R3. Neuro-Symbolic Audit & In-Memory Multi-Gate Verifier (Stages 3B & 4)
Seed `codedee_server/data/mini_test_knowledges.json` into a local ChromaDB collection containing CWE-89 descriptions, vulnerability patterns, and language-specific sanitizers (e.g. parameterized queries for Python psycopg2/sqlite3, JS pg/mysql2, TS TypeORM/Prisma).
Implement a Program Slicer performing full function / method extraction for complete source and sink context.
Implement the Neural Oracle querying a live local Ollama instance running `qwen2.5-coder:7b` with code slice, CWE-89 metadata, and RAG context, returning structured JSON with `confidence_score` (0.0–1.0), `risk_level`, `sanitizer_detected`, and `reasoning` (flagging low-confidence items for review without hard deletion).
Implement the In-Memory Multi-Gate Verifier executing:
- Gate 1: Tree-sitter CST syntax validity check.
- Gate 2: Interface preservation check (function name and argument types must remain identical).
- Gate 3: Taint sink neutralization check (direct concatenation removed).
- Gate 4: Maintainability non-regression check (delta CC <= 0).
- Gate 6: SAST re-scan check (zero new flaws).
Retain and return only patch candidates that pass 100% of the verification gates.

### R4. VS Code Extension (`codedee_extension/`)
Scaffold `codedee_extension/` with `package.json`, `tsconfig.json`, and VS Code extension dependencies.
Implement extension activation and configuration:
- Setting for Backend Server URL (default `http://127.0.0.1:8000`).
- Command: `CodeDEE: Scan Current File / Project`.
Build an interactive Webview Panel displaying detected CWE-89 issues, taint paths (Source -> Steps -> Sink), risk level, AI reasoning, and a `[Request AI Patches]` button.
Implement Diff Viewer & Patch Application:
- Invokes `/api/generate-patches` on button click.
- Renders verified candidate patches in VS Code's native diff viewer (`vscode.diff`).
- Provides an `[Apply Patch]` button invoking `/api/apply-patch` to update the active document.

## Acceptance Criteria

### Automated Test Suite
- [ ] `pytest` passes in `codedee_server/` covering:
  - Dataset extraction and schema validation for `mini_test_datasets.json`.
  - Tree-sitter CST parsing and NetworkX graph builders (Call Graph, CFG, DFG) for Python, JavaScript, and TypeScript.
  - Maintainability Engine computing exactly the 8 specified metrics.
  - Symbolic Taint Walker identifying SQL injection taint paths from source to sink.
  - Multi-Gate Verifier validation (Gates 1, 2, 3, 4, 6).
  - FastAPI endpoints (`/health`, `/api/scan`, `/api/generate-patches`, `/api/apply-patch`).
- [ ] TypeScript compilation (`npm run compile`) in `codedee_extension/` succeeds with zero errors.

### End-to-End Integration Verification
- [ ] An end-to-end integration test runs against vulnerable Python and JavaScript SQL Injection samples from `mini_test_datasets.json`:
  - `POST /api/scan` flags the CWE-89 vulnerability and outputs the complete taint path and maintainability metrics.
  - `POST /api/generate-patches` with live Ollama `qwen2.5-coder:7b` generates candidate patches that pass all in-memory verification gates (Gates 1, 2, 3, 4, 6).
  - `POST /api/apply-patch` successfully applies the verified patch to the target source file.
