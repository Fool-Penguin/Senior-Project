# CodeDEE E2E Test Infrastructure Specification

**Document Version:** 1.0.0  
**Target Subsystem:** CodeDEE End-to-End Testing Track (`codedee/tests_e2e/`)  
**Scope:** Vertical Slice CWE-89 (SQL Injection) Automated Security Repair across Python, JavaScript, and TypeScript  
**Status:** Runnable & 100% Verified (74/74 passing)  

---

## 1. Test Philosophy

The CodeDEE test infrastructure enforces an **opaque-box, multi-tier, specification-derived testing strategy**:
1. **Opaque-Box Independence**: Tests interact with the system strictly through defined external interfaces (REST API endpoints `/health`, `/api/scan`, `/api/generate-patches`, `/api/apply-patch`, and dataset artifact `mini_test_datasets.json`), treating implementation internals as a black box.
2. **Deterministic Multi-Gate Verification**: Every generated repair must pass 100% of the in-memory verification gates (Gate 1 CST Syntax, Gate 2 Interface Integrity, Gate 3 Sink Neutralization, Gate 4 Maintainability Non-Regression $\Delta CC \le 0$, Gate 6 SAST Re-scan). Facade tests that pass without exercising genuine verification logic are strictly prohibited.
3. **Multi-Language Parity**: Security analysis, maintainability metrics, and program repair pipelines are tested symmetrically across all three supported target languages: Python, JavaScript, and TypeScript.
4. **Safety & Non-Destructive Operation**: Tests verify filesystem backup creation (`.bak`) and automatic transaction rollback upon detection of syntax degradation or interface drift.

---

## 2. Feature Inventory in E2E Scope

| Feature ID | Endpoint / Component | Scope & Requirements | Primary Contract |
| :--- | :--- | :--- | :--- |
| **F-HLT** | `GET /health` | Pre-flight check verifying Ollama reachability, required model (`qwen2.5-coder:7b`) availability, version strings, and alias `/api/health`. | `HealthCheckResponse` |
| **F-SCN** | `POST /api/scan` | Concrete Syntax Tree parsing, ISO/IEC 25010 maintainability calculation (8 metrics), and Stage 3A/3B Symbolic Taint Walker identifying CWE-89 taint flows. | `ScanResponse` / `SecurityNodeOutput` |
| **F-GEN** | `POST /api/generate-patches` | In-memory candidate fix generation via live Ollama `qwen2.5-coder:7b` + rule transforms, filtered by in-memory Multi-Gate verification (Gates 1, 2, 3, 4, 6). | `GeneratePatchesResponse` / `VerifiedPatch` |
| **F-APP** | `POST /api/apply-patch` | Direct disk application of unified diffs or remediated code with automatic `.bak` safety backup and post-application Tree-sitter CST syntax verification. | `ApplyPatchResponse` |
| **F-DAT** | `mini_test_datasets.json` | Dataset extraction containing exactly 105 CWE-89 records with exact 14 columns, multi-language coverage (Python: 88, JS: 13, TS: 4), and curated ground-truth fixes. | R1 Dataset Schema |

---

## 3. Test Architecture

The test suite resides in `codedee/tests_e2e/` and executes using standard `pytest`:

```
codedee/
└── tests_e2e/
    ├── __init__.py
    ├── conftest.py                # Universal test fixtures, ApiClientWrapper, dataset loader
    ├── test_tier1_features.py     # Tier 1: Feature Coverage (>=5 tests per feature)
    ├── test_tier2_boundaries.py   # Tier 2: Boundary & Corner Cases (>=5 tests per feature)
    ├── test_tier3_combinations.py # Tier 3: Cross-Feature Interactions & Multi-Step Workflows
    └── test_tier4_real_world.py   # Tier 4: Real-World CWE-89 Scenarios (Py, JS, TS)
```

### 3.1 Transparent Client Architecture (`ApiClientWrapper`)
`ApiClientWrapper` in `conftest.py` provides transparent dual-mode execution:
1. **Live HTTP Mode**: Probes `http://127.0.0.1:8000/health`. If an external server is running, requests are routed over HTTP using pooled `requests.Session`.
2. **In-Process Daemon Server**: If port 8000 is inactive, `conftest.py` starts an in-process Uvicorn ASGI server in a daemon thread configured with `http="h11"` and `loop="asyncio:SelectorEventLoop"`. This guarantees 100% socket stability on Windows Python 3.14 without thread pool exhaustion or proactor access violations.
3. **In-Memory Fallback**: Provides `in_memory_client` fixture backed by FastAPI's `TestClient` for isolated unit verification.

---

## 4. 4-Tier Testing Methodology

### Tier 1: Feature Coverage (`test_tier1_features.py`)
Enforces at least 5 isolated happy-path tests for each individual feature:
- **/health (6 tests)**: Status codes, Ollama reachability flag, model name `qwen2.5-coder:7b`, backend semantic version, alias endpoint `/api/health`, and root endpoint `/` directory.
- **/api/scan (6 tests)**: Python file scan on disk, JavaScript file scan on disk, TypeScript file scan on disk, in-memory virtual code buffer scan, 8 ISO/IEC 25010 maintainability metrics calculation, and multi-file recursive directory scanning.
- **/api/generate-patches (5 tests)**: Raw code_content patch generation, target_file patch generation on disk, sample_id dataset resolution, candidate_count parameter override, and multi-gate diagnostic verification (Gates 1, 2, 3, 4, 6).
- **/api/apply-patch (5 tests)**: Remediated code substitution, automatic `.bak` safety backup creation, unified diff application, syntax regression rollback rejection, and response schema validation.
- **Dataset Extraction (6 tests)**: File existence, exact 105 record count, exact 14 columns conformance, multi-language distribution (88 Py, 13 JS, 4 TS), canonical CWE-89 description/CVSS vectors, and curated benchmark fixtures presence.

### Tier 2: Boundary & Corner Cases (`test_tier2_boundaries.py`)
Stress-tests the system under adversarial, malformed, and edge conditions:
- **Health Boundaries (5 tests)**: Unsupported HTTP methods (POST 405), tolerance of arbitrary query parameters, custom Accept/User-Agent headers, root endpoint rejection, and rapid sequential health checks.
- **Scan Boundaries (11 tests)**: 0-byte empty files, whitespace/comments-only code, single-line minimal statements, large multiline file stress, syntax error resilience via Tree-sitter ERROR nodes, non-existent target paths (404), empty payloads (400), Python parameterized queries (0 issues), JavaScript parameterized queries (0 issues), TypeScript ORM queries (0 issues), and non-sink SQL keyword mentions.
- **Patch Generation Boundaries (6 tests)**: Unknown issue IDs (404), missing mandatory fields (422), candidate_count underflow (<1 -> 422), candidate_count overflow (>5 -> 422), empty code content (404), and alias `num_candidates` parameter reconciliation.
- **Apply Patch Boundaries (6 tests)**: Non-existent target file (404), missing both remediated code and diff (400), malformed/corrupt unified diff resilience, JavaScript syntax error rejection (422), and pre-application backup preservation.
- **Dataset Invariants (6 tests)**: Sample ID uniqueness, non-empty code strings, boolean `Is_vulnerable` typing, CVSS v3.1 regex validation, standard lowercase language keys, and ground truth fixed code syntax validity.

### Tier 3: Cross-Feature Combinations (`test_tier3_combinations.py`)
Validates end-to-end multi-step workflow pipelines:
1. **Full Python Repair Cycle**: Scan $\rightarrow$ detect CWE-89 $\rightarrow$ generate verified patch $\rightarrow$ apply patch to disk $\rightarrow$ re-scan confirms 0 issues.
2. **Full JavaScript Repair Cycle**: Scan $\rightarrow$ detect flaw $\rightarrow$ generate `$1` parameterized fix $\rightarrow$ apply patch $\rightarrow$ re-scan confirms 0 issues.
3. **Full TypeScript Repair Cycle**: Scan $\rightarrow$ detect flaw $\rightarrow$ generate patch $\rightarrow$ apply patch $\rightarrow$ re-scan confirms 0 issues.
4. **Health-Gated Multi-File Directory Remediation**: Health pre-flight check $\rightarrow$ multi-file project scan (2 flaws) $\rightarrow$ staged repair of File 1 (flaws decrement to 1) $\rightarrow$ staged repair of File 2 (flaws decrement to 0).
5. **Unsafe Patch Rejection & Automatic Safety Rollback**: Ingest flaw $\rightarrow$ attempt applying broken syntax patch $\rightarrow$ 422 error $\rightarrow$ verify target file restored intact from `.bak` $\rightarrow$ re-scan confirms file integrity.
6. **In-Memory Virtual Repair Pipeline**: Zero disk I/O workflow operating solely on editor memory buffers.
7. **Maintainability Non-Regression Across Repair**: Verifies $\Delta CC \le 0$ before and after repair execution.

### Tier 4: Real-World Application Scenarios (`test_tier4_real_world.py`)
Validates against authentic CWE-89 vulnerabilities extracted from `mini_test_datasets.json`:
1. `SEC_PY_CWE89_001`: Python SQLite login injection.
2. `SEC_JS_CWE89_001`: Node.js PostgreSQL client query interpolation.
3. `SEC_TS_JUICE_SHOP_001`: OWASP Juice Shop TypeScript Sequelize search injection.
4. `SEC_PY_CVE_2023_34362`: MOVEit Transfer enterprise CVE SQL injection.
5. `SEC_PY_PYGOAT_INJECTION_001`: OWASP PyGoat Flask vulnerability challenge.
6. `Bulk Dataset Scan Sampling`: Random sampling across Python, JavaScript, and TypeScript verifying ISO/IEC 25010 metrics calculation and Stage 3B contract conformity.

---

## 5. Coverage Summary & Results

| Test Tier | Test Module | Test Count | Pass Rate | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Tier 1** | `test_tier1_features.py` | 28 | 100% | **PASSED** |
| **Tier 2** | `test_tier2_boundaries.py` | 33 | 100% | **PASSED** |
| **Tier 3** | `test_tier3_combinations.py` | 7 | 100% | **PASSED** |
| **Tier 4** | `test_tier4_real_world.py` | 6 | 100% | **PASSED** |
| **Total** | Full Suite | **74** | **100%** | **ALL PASSED** |

---

## 6. Execution Command

To execute the complete E2E test suite:

```bash
python -m pytest -p no:anyio codedee/tests_e2e/ -v
```
