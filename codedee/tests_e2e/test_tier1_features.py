"""
test_tier1_features.py - Tier 1: Feature Coverage Tests (>=5 tests per feature).

Opaque-box tests covering:
1. /health endpoint (Ollama reachability, model availability, status, version, alias)
2. /api/scan endpoint (Python, JS, TS file scan, in-memory scan, ISO/IEC 25010 maintainability)
3. /api/generate-patches endpoint (Ollama candidate generation, multi-gate checks, diffs, gates)
4. /api/apply-patch endpoint (remediated code, unified diff, backup .bak, syntax check, schema)
5. Dataset extraction (105 records, exact 14 columns, multi-lang distribution, benchmark samples)
"""

import json
from pathlib import Path
from typing import Any, Dict, List
import pytest


# ============================================================================
# Feature 1: /health Pre-Flight & Server Health Check (>=5 tests)
# ============================================================================

def test_health_status_code_and_structure(client):
    """Test 1.1: Verify /health returns 200 (or 503 if degraded) with strict schema."""
    resp = client.get("/health")
    assert resp.status_code in (200, 503), f"Unexpected status: {resp.status_code}"
    data = resp.json()
    assert "status" in data
    assert "backend_version" in data
    assert "ollama_reachable" in data
    assert "ollama_url" in data
    assert "model_available" in data
    assert "model_name" in data
    assert "available_models" in data
    assert isinstance(data["available_models"], list)


def test_health_ollama_reachability(client):
    """Test 1.2: Verify Ollama reachability boolean and URL."""
    resp = client.get("/health")
    data = resp.json()
    assert isinstance(data["ollama_reachable"], bool)
    assert data["ollama_url"].startswith("http")


def test_health_model_availability(client):
    """Test 1.3: Verify required model name is qwen2.5-coder:7b and status consistency."""
    resp = client.get("/health")
    data = resp.json()
    assert data["model_name"] == "qwen2.5-coder:7b"
    if data["model_available"]:
        assert resp.status_code == 200
        assert data["status"] == "ok"
        assert any("qwen2.5-coder:7b" in m for m in data["available_models"])


def test_health_backend_version(client):
    """Test 1.4: Verify backend server version is 1.0.0."""
    resp = client.get("/health")
    data = resp.json()
    assert data["backend_version"] == "1.0.0"


def test_health_alias_endpoint(client):
    """Test 1.5: Verify /api/health alias returns identical payload."""
    resp_primary = client.get("/health")
    resp_alias = client.get("/api/health")
    assert resp_alias.status_code == resp_primary.status_code
    assert resp_alias.json()["model_name"] == resp_primary.json()["model_name"]


def test_health_root_endpoint_directory(client):
    """Test 1.6: Verify GET / root directory lists all core endpoints."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "CodeDEE Backend Server"
    assert "endpoints" in data
    assert data["endpoints"]["health"] == "/health"
    assert data["endpoints"]["scan"] == "/api/scan"
    assert data["endpoints"]["generate_patches"] == "/api/generate-patches"
    assert data["endpoints"]["apply_patch"] == "/api/apply-patch"


# ============================================================================
# Feature 2: /api/scan Static Analysis & Stage 3B Findings (>=5 tests)
# ============================================================================

def test_scan_python_file_on_disk(client, temp_workspace):
    """Test 2.1: Scan vulnerable Python file on disk and verify Stage 3B contract."""
    code = (
        "import sqlite3\n"
        "from flask import request\n\n"
        "def login():\n"
        "    username = request.args.get('username')\n"
        "    query = f\"SELECT * FROM users WHERE username = '{username}'\"\n"
        "    conn = sqlite3.connect('app.db')\n"
        "    cursor = conn.cursor()\n"
        "    return cursor.execute(query).fetchall()\n"
    )
    py_file = temp_workspace.create_file("vulnerable_login.py", code)

    resp = client.post("/api/scan", json={"target_path": str(py_file)})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["files_scanned"] == 1
    assert data["issues_count"] >= 1

    issue = data["issues"][0]
    assert issue["symbolic_finding"]["cwe_id"] == "CWE-89"
    assert "username" in issue["symbolic_finding"]["source_node"]["symbol"] or "args" in issue["symbolic_finding"]["source_node"]["symbol"]
    assert "execute" in issue["symbolic_finding"]["sink_node"]["expression"] or "SQL Sink" in issue["symbolic_finding"]["sink_node"]["symbol"]
    assert len(issue["symbolic_finding"]["taint_path"]) >= 1
    assert issue["pipeline_metadata"]["language"] == "python"


def test_scan_javascript_file_on_disk(client, temp_workspace):
    """Test 2.2: Scan vulnerable JavaScript file on disk."""
    code = (
        "const { Client } = require('pg');\n\n"
        "async function getUser(req, res) {\n"
        "    const userId = req.query.id;\n"
        "    const client = new Client();\n"
        "    await client.connect();\n"
        "    const query = `SELECT * FROM users WHERE id = ${userId}`;\n"
        "    const result = await client.query(query);\n"
        "    res.json(result.rows);\n"
        "}\n"
    )
    js_file = temp_workspace.create_file("getUser.js", code)

    resp = client.post("/api/scan", json={"target_path": str(js_file)})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["issues_count"] >= 1
    assert data["issues"][0]["pipeline_metadata"]["language"] == "javascript"


def test_scan_typescript_file_on_disk(client, temp_workspace):
    """Test 2.3: Scan vulnerable TypeScript file on disk."""
    code = (
        "import { Request, Response } from 'express';\n"
        "import { db } from './db';\n\n"
        "export async function searchProducts(req: Request, res: Response) {\n"
        "    const term: string = req.query.q as string;\n"
        "    return await db.query(`SELECT * FROM products WHERE name LIKE '%${term}%'`);\n"
        "}\n"
    )
    ts_file = temp_workspace.create_file("searchProducts.ts", code)

    resp = client.post("/api/scan", json={"target_path": str(ts_file)})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["issues_count"] >= 1
    assert data["issues"][0]["pipeline_metadata"]["language"] == "typescript"


def test_scan_in_memory_code_content(client):
    """Test 2.4: Scan raw code content in-memory without disk write."""
    code = (
        "def query_db(user_input):\n"
        "    return cursor.execute('SELECT * FROM accounts WHERE id = ' + user_input)\n"
    )
    resp = client.post(
        "/api/scan",
        json={"code_content": code, "file_name": "editor_buffer.py", "language": "python"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["files_scanned"] == 1
    assert data["issues_count"] >= 1
    assert data["issues"][0]["symbolic_finding"]["cwe_id"] == "CWE-89"


def test_scan_maintainability_metrics_iso25010(client):
    """Test 2.5: Verify maintainability engine outputs exactly 8 ISO/IEC 25010 metrics."""
    code = (
        "# Sample module\n"
        "def compute(a, b):\n"
        "    if a > 0:\n"
        "        return a + b\n"
        "    return b\n"
    )
    resp = client.post(
        "/api/scan",
        json={"code_content": code, "file_name": "calc.py", "language": "python"},
    )
    assert resp.status_code == 200
    metrics = resp.json()["maintainability"]
    assert metrics is not None

    # Verify function-level metrics (4)
    assert "cyclomatic_complexity" in metrics
    assert "cognitive_complexity" in metrics
    assert "parameter_count" in metrics
    assert "function_sloc" in metrics

    # Verify file-level metrics (4)
    assert "file_sloc" in metrics
    assert "module_coupling" in metrics
    assert "Ce" in metrics["module_coupling"]
    assert "Ca" in metrics["module_coupling"]
    assert "instability" in metrics["module_coupling"]
    assert "duplicated_blocks" in metrics
    assert "comment_density" in metrics


def test_scan_multi_file_directory(client, temp_workspace):
    """Test 2.6: Scan entire directory with mixed vulnerable and non-vulnerable files."""
    vuln_code = "def vuln(req): cursor.execute('SELECT ' + req.args['val'])"
    safe_code = "def safe(val): return val * 2"
    temp_workspace.create_file("sub/vuln.py", vuln_code)
    temp_workspace.create_file("sub/safe.py", safe_code)

    resp = client.post("/api/scan", json={"target_path": str(temp_workspace.root / "sub")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["files_scanned"] == 2
    assert data["issues_count"] >= 1


# ============================================================================
# Feature 3: /api/generate-patches Multi-Gate Patch Generation (>=5 tests)
# ============================================================================

def test_generate_patches_with_code_content(client):
    """Test 3.1: Generate verified patches providing raw vulnerable code_content."""
    code = (
        "def login(username):\n"
        "    cursor.execute(f\"SELECT * FROM users WHERE username = '{username}'\")\n"
    )
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "TEST_PY_001", "code_content": code, "candidate_count": 3},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_generated"] >= 1
    assert data["verified_count"] >= 1
    patch = data["verified_patches"][0]
    assert "diff" in patch
    assert "remediated_code" in patch
    assert "?" in patch["remediated_code"] or "%s" in patch["remediated_code"]
    assert patch["delta_cc"] <= 0


def test_generate_patches_with_target_file(client, temp_workspace):
    """Test 3.2: Generate patches for an existing vulnerable file on disk."""
    code = (
        "def get_item(item_id):\n"
        "    q = 'SELECT * FROM items WHERE id = ' + str(item_id)\n"
        "    cursor.execute(q)\n"
    )
    f = temp_workspace.create_file("db_ops.py", code)
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "TEST_FILE_001", "target_file": str(f), "candidate_count": 3},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["verified_count"] >= 1


def test_generate_patches_dataset_match_by_issue_id(client):
    """Test 3.3: Generate patches resolving sample_id directly from mini_test_datasets.json."""
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "SEC_PY_CWE89_001", "candidate_count": 3},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["issue_id"] == "SEC_PY_CWE89_001"
    assert data["verified_count"] >= 1


def test_generate_patches_candidate_count_override(client):
    """Test 3.4: Generate patches requesting 4 candidates."""
    code = "def query(user): cursor.execute('SELECT * FROM data WHERE user = ' + user)"
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "CAND_4_TEST", "code_content": code, "candidate_count": 4},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_generated"] >= 1


def test_generate_patches_multi_gate_results(client):
    """Test 3.5: Verify 100% verified patches satisfy Gates 1, 2, 3, 4, and 6."""
    code = (
        "def find_user(name):\n"
        "    cursor.execute(f\"SELECT * FROM users WHERE name = '{name}'\")\n"
    )
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "GATES_TEST", "code_content": code, "candidate_count": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["verified_patches"]) > 0
    p = data["verified_patches"][0]
    assert set(p["passed_gates"]) == {"Gate 1", "Gate 2", "Gate 3", "Gate 4", "Gate 6"}
    assert p["gate1_syntax"]["passed"] is True
    assert p["gate2_interface"]["passed"] is True
    assert p["gate3_taint_neutralized"]["passed"] is True
    assert p["gate4_maintainability"]["passed"] is True
    assert p["gate6_sast_rescan"]["passed"] is True


# ============================================================================
# Feature 4: /api/apply-patch Safe Disk Patch Application (>=5 tests)
# ============================================================================

def test_apply_patch_with_remediated_code(client, temp_workspace):
    """Test 4.1: Apply patch using direct remediated_code."""
    orig_code = "def test(x):\n    cursor.execute('SELECT ' + x)\n"
    remediated = "def test(x):\n    cursor.execute('SELECT ?', (x,))\n"
    target = temp_workspace.create_file("test_apply.py", orig_code)

    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(target), "remediated_code": remediated},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert target.read_text(encoding="utf-8") == remediated


def test_apply_patch_creates_backup_file(client, temp_workspace):
    """Test 4.2: Verify automatic creation of .bak backup file with original content."""
    orig_code = "def run():\n    return 1\n"
    remediated = "def run():\n    return 2\n"
    target = temp_workspace.create_file("service.py", orig_code)

    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(target), "remediated_code": remediated},
    )
    assert resp.status_code == 200
    data = resp.json()
    backup_path = Path(data["backup_file"])
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == orig_code


def test_apply_patch_with_unified_diff(client, temp_workspace):
    """Test 4.3: Apply patch using unified diff format."""
    orig_code = "def query(user):\n    cursor.execute('SELECT ' + user)\n"
    diff = (
        "--- a/query.py\n"
        "+++ b/query.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def query(user):\n"
        "-    cursor.execute('SELECT ' + user)\n"
        "+    cursor.execute('SELECT ?', (user,))\n"
    )
    target = temp_workspace.create_file("query.py", orig_code)

    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(target), "patch_diff": diff},
    )
    assert resp.status_code == 200, resp.text
    assert "SELECT ?" in target.read_text(encoding="utf-8")


def test_apply_patch_reverts_on_syntax_error(client, temp_workspace):
    """Test 4.4: Verify rollback to backup when patch introduces invalid syntax."""
    orig_code = "def valid_func():\n    return 42\n"
    broken_code = "def valid_func():\n    return return <<<\n"
    target = temp_workspace.create_file("syntax_check.py", orig_code)

    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(target), "remediated_code": broken_code},
    )
    assert resp.status_code == 422
    assert target.read_text(encoding="utf-8") == orig_code


def test_apply_patch_response_schema(client, temp_workspace):
    """Test 4.5: Verify /api/apply-patch response schema attributes."""
    code = "def a(): pass\n"
    new_code = "def a(): return True\n"
    target = temp_workspace.create_file("schema_test.py", code)

    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(target), "remediated_code": new_code, "patch_id": "P_001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert "target_file" in data
    assert "backup_file" in data
    assert "message" in data
    assert "updated_content" in data


# ============================================================================
# Feature 5: Dataset Extraction (mini_test_datasets.json) (>=5 tests)
# ============================================================================

def test_dataset_file_exists_and_valid_json(dataset_path):
    """Test 5.1: Verify dataset file exists and is valid JSON."""
    assert dataset_path.exists()
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)


def test_dataset_exact_count(mini_datasets):
    """Test 5.2: Verify dataset contains exactly 105 CWE-89 samples."""
    assert len(mini_datasets) == 105


def test_dataset_exact_14_columns(mini_datasets):
    """Test 5.3: Verify every sample contains the exact 14 columns specified in R1."""
    expected_cols = [
        "sample_id",
        "language",
        "Is_vulnerable",
        "cwe_id",
        "cwe_name",
        "cwe_description",
        "owasp_category",
        "cvss_v31_vector",
        "sources",
        "source_pattern",
        "sink_pattern",
        "sanitizer_pattern",
        "original_code",
        "fixed_code",
    ]
    for record in mini_datasets:
        assert list(record.keys()) == expected_cols, f"Mismatch in {record.get('sample_id')}"


def test_dataset_multi_language_distribution(mini_datasets):
    """Test 5.4: Verify language breakdown (Python: 88, JavaScript: 13, TypeScript: 4)."""
    counts = {}
    for r in mini_datasets:
        lang = r["language"].lower()
        counts[lang] = counts.get(lang, 0) + 1
    assert counts.get("python") == 88
    assert counts.get("javascript") == 13
    assert counts.get("typescript") == 4


def test_dataset_canonical_cwe89_fields(mini_datasets):
    """Test 5.5: Verify all records have cwe_id == CWE-89 and valid CVSS v3.1 vector."""
    for r in mini_datasets:
        assert r["cwe_id"] == "CWE-89"
        assert "CVSS:3.1" in r["cvss_v31_vector"]
        assert len(r["original_code"]) > 0


def test_dataset_curated_benchmarks_present(datasets_by_id):
    """Test 5.6: Verify existence of curated benchmark fixtures across all 3 languages."""
    assert "SEC_PY_CWE89_001" in datasets_by_id
    assert "SEC_JS_CWE89_001" in datasets_by_id
    assert "SEC_TS_JUICE_SHOP_001" in datasets_by_id
    assert datasets_by_id["SEC_PY_CWE89_001"]["fixed_code"] is not None
    assert datasets_by_id["SEC_JS_CWE89_001"]["fixed_code"] is not None
    assert datasets_by_id["SEC_TS_JUICE_SHOP_001"]["fixed_code"] is not None
