"""
test_api.py - Comprehensive API tests for CodeDEE Backend Server.

Validates:
1. GET /health with live Ollama reachability and qwen2.5-coder:7b verification.
2. POST /api/scan with CST parsing, 8 maintainability metrics, and Stage 3B contract conformance.
3. POST /api/generate-patches with live/in-memory Multi-Gate verification (Gates 1, 2, 3, 4, 6).
4. POST /api/apply-patch with disk safety backups (.bak) and CST syntax validation.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.contracts import SecurityNodeOutput

client = TestClient(app)


# ============================================================================
# 1. Root & Health Endpoint Tests
# ============================================================================

def test_root_endpoint():
    """Verify server metadata and root route."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "endpoints" in data


def test_health_endpoint_live_ollama():
    """Verify GET /health pre-flight check connects to Ollama and finds qwen2.5-coder:7b."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["backend_version"] == "1.0.0"
    assert data["ollama_reachable"] is True
    assert data["model_available"] is True
    assert data["model_name"] == "qwen2.5-coder:7b"
    assert isinstance(data["available_models"], list)
    assert any("qwen2.5-coder:7b" in m for m in data["available_models"])


def test_health_endpoint_unreachable_fallback(monkeypatch):
    """Verify GET /health returns 503 when Ollama is unreachable."""
    from app.api import health

    # Monkeypatch to invalid port
    monkeypatch.setattr(health, "OLLAMA_BASE_URL", "http://127.0.0.1:59999")
    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["ollama_reachable"] is False
    assert data["model_available"] is False
    assert data["status"] == "unhealthy"


# ============================================================================
# 2. Scan Endpoint Tests (Stage 3B Contract)
# ============================================================================

VULN_PYTHON_SNIPPET = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""

SAFE_PYTHON_SNIPPET = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = "SELECT id, role, email FROM accounts WHERE username = ?"
    cursor.execute(query, (username,))
    return cursor.fetchall()
"""

VULN_JS_SNIPPET = """function searchProducts(req, res) {
    const term = req.query.term;
    const query = `SELECT * FROM products WHERE name LIKE '%${term}%'`;
    db.query(query, function(err, results) {
        res.json(results);
    });
}
"""


def test_scan_vulnerable_python_buffer():
    """Verify POST /api/scan flags CWE-89 and returns valid Stage 3B contract output."""
    payload = {
        "code_content": VULN_PYTHON_SNIPPET,
        "file_name": "auth_controller.py",
        "language": "python",
    }
    response = client.post("/api/scan", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["files_scanned"] == 1
    assert data["issues_count"] >= 1
    assert len(data["issues"]) >= 1

    issue = data["issues"][0]
    # Validate against strict Pydantic model
    validated_issue = SecurityNodeOutput.model_validate(issue)

    assert validated_issue.issue_id.startswith("ISSUE-CWE89-")
    assert validated_issue.target_file == "auth_controller.py"

    # Symbolic finding verification
    sym = validated_issue.symbolic_finding
    assert sym.cwe_id == "CWE-89"
    assert "SQL Injection" in sym.cwe_name
    assert sym.severity == "HIGH"
    assert sym.sanitized is False
    assert len(sym.taint_path) >= 2
    assert sym.source_node.get("file") == "auth_controller.py"
    assert sym.sink_node.get("line") is not None

    # Neuro assessment verification
    neuro = validated_issue.neuro_assessment
    assert neuro is not None
    assert 0.0 <= neuro.confidence_score <= 1.0
    assert neuro.risk_level in ("CRITICAL", "HIGH")
    assert neuro.sanitizer_detected is False
    assert len(neuro.reasoning) > 10

    # Pipeline metadata verification (ISO/IEC 25010 8 metrics)
    meta = validated_issue.pipeline_metadata
    metrics = meta.maintainability_metrics
    assert "cyclomatic_complexity" in metrics
    assert "cognitive_complexity" in metrics
    assert "parameter_count" in metrics
    assert "function_sloc" in metrics
    assert "file_sloc" in metrics
    assert "module_coupling" in metrics
    assert "duplicated_blocks" in metrics
    assert "comment_density" in metrics


def test_scan_vulnerable_javascript_buffer():
    """Verify POST /api/scan flags CWE-89 in JavaScript."""
    payload = {
        "code_content": VULN_JS_SNIPPET,
        "file_name": "products.js",
        "language": "javascript",
    }
    response = client.post("/api/scan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["issues_count"] >= 1
    assert data["issues"][0]["symbolic_finding"]["cwe_id"] == "CWE-89"


def test_scan_safe_sanitized_buffer():
    """Verify POST /api/scan reports 0 issues for parameterized safe queries."""
    payload = {
        "code_content": SAFE_PYTHON_SNIPPET,
        "file_name": "safe_auth.py",
        "language": "python",
    }
    response = client.post("/api/scan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["issues_count"] == 0
    assert len(data["issues"]) == 0


def test_scan_disk_file(tmp_path):
    """Verify POST /api/scan works with disk file target_path."""
    sample_file = tmp_path / "vulnerable_disk.py"
    sample_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    payload = {"target_path": str(sample_file)}
    response = client.post("/api/scan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["files_scanned"] == 1
    assert data["issues_count"] >= 1


def test_scan_nonexistent_path():
    """Verify POST /api/scan returns 404 for invalid path."""
    response = client.post("/api/scan", json={"target_path": "non/existent/path/file.py"})
    assert response.status_code == 404


# ============================================================================
# 3. Generate Patches Endpoint Tests (Multi-Gate Verifier)
# ============================================================================

def test_generate_patches_multi_gate_verified():
    """Verify POST /api/generate-patches produces 100% verified patches."""
    payload = {
        "issue_id": "ISSUE-CWE89-TEST01",
        "target_file": "auth_controller.py",
        "candidate_count": 3,
        "code_content": VULN_PYTHON_SNIPPET,
    }
    response = client.post("/api/generate-patches", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["issue_id"] == "ISSUE-CWE89-TEST01"
    assert data["total_generated"] >= 1
    assert data["verified_count"] >= 1
    assert len(data["verified_patches"]) >= 1

    patch = data["verified_patches"][0]
    # Check all gates are passed
    assert patch["passed_gates"] == ["Gate 1", "Gate 2", "Gate 3", "Gate 4", "Gate 6"]
    assert patch["delta_cc"] <= 0
    assert "diff" in patch and len(patch["diff"]) > 0
    assert "remediated_code" in patch and len(patch["remediated_code"]) > 0
    # Gate detail assertions
    assert patch["gate1_syntax"]["passed"] is True
    assert patch["gate2_interface"]["passed"] is True
    assert patch["gate3_taint_neutralized"]["passed"] is True
    assert patch["gate4_maintainability"]["passed"] is True
    assert patch["gate6_sast_rescan"]["passed"] is True


def test_generate_patches_benchmark_dataset_fixture():
    """Verify patch generation against SEC_PY_CWE89_001 from mini_test_datasets.json."""
    payload = {
        "issue_id": "SEC_PY_CWE89_001",
        "candidate_count": 3,
    }
    response = client.post("/api/generate-patches", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verified_count"] >= 1
    assert len(data["verified_patches"]) >= 1


# ============================================================================
# 4. Apply Patch Endpoint Tests
# ============================================================================

def test_apply_patch_success(tmp_path):
    """Verify POST /api/apply-patch modifies target file, creates .bak, and verifies syntax."""
    target_file = tmp_path / "app_login.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    payload = {
        "target_file": str(target_file),
        "patch_id": "patch_cand_01",
        "remediated_code": SAFE_PYTHON_SNIPPET,
    }
    response = client.post("/api/apply-patch", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["target_file"] == str(target_file)
    assert data["backup_file"] == str(target_file) + ".bak"

    # Verify backup exists and contains original code
    backup_file = Path(data["backup_file"])
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET

    # Verify target file has been updated
    assert target_file.read_text(encoding="utf-8") == SAFE_PYTHON_SNIPPET


def test_apply_patch_syntax_error_rejection(tmp_path):
    """Verify POST /api/apply-patch rejects broken syntax and restores from backup."""
    target_file = tmp_path / "app_broken.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    # Invalid Python code with syntax error
    malformed_code = "def broken_func(:\n    invalid syntax !!"

    payload = {
        "target_file": str(target_file),
        "remediated_code": malformed_code,
    }
    response = client.post("/api/apply-patch", json=payload)
    assert response.status_code == 422
    assert "invalid CST syntax" in response.json()["detail"]

    # Verify target file was reverted to original content
    assert target_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET


def test_apply_patch_missing_file():
    """Verify POST /api/apply-patch returns 404 for missing target file."""
    response = client.post(
        "/api/apply-patch",
        json={"target_file": "missing_file.py", "remediated_code": SAFE_PYTHON_SNIPPET},
    )
    assert response.status_code == 404


def test_apply_patch_unified_diff_roundtrip(tmp_path):
    """
    Verify complete patch generation and unified diff application roundtrip:
    1. Seed vulnerable Python code into a target file on disk.
    2. Call POST /api/generate-patches to generate verified patch candidates.
    3. Extract the generated unified diff from verified_patches.
    4. Assert that the diff has standard unified diff headers with clean line breaks.
    5. Send the exact diff to POST /api/apply-patch with {"patch_diff": diff}.
    6. Assert API returns HTTP 200 with success=True and valid backup file.
    7. Assert target file on disk is genuinely updated to parameterized query.
    8. Assert vulnerable f-string is eliminated from disk.
    9. Assert safety backup contains the exact original unpatched code.
    """
    target_file = tmp_path / "vulnerable_auth.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    # Step 1: Call POST /api/generate-patches
    gen_payload = {
        "issue_id": "ISSUE-CWE89-ROUNDTRIP-01",
        "target_file": str(target_file),
        "candidate_count": 3,
        "code_content": VULN_PYTHON_SNIPPET,
    }
    gen_response = client.post("/api/generate-patches", json=gen_payload)
    assert gen_response.status_code == 200
    gen_data = gen_response.json()

    assert gen_data["verified_count"] >= 1
    assert len(gen_data["verified_patches"]) >= 1

    # Step 2: Extract verified patch and diff
    patch = gen_data["verified_patches"][0]
    diff = patch["diff"]
    remediated_code = patch["remediated_code"]
    assert isinstance(diff, str) and len(diff) > 0

    # Step 3: Validate standard unified diff formatting (clean newlines)
    assert diff.startswith("--- "), f"Diff must start with '--- ', got: {diff[:40]}"
    assert "\n+++ " in diff, f"Diff must have newline before '+++ ', got: {diff[:80]}"
    assert "\n@@ " in diff, f"Diff must have newline before hunk header '@@ ', got: {diff[:120]}"
    diff_lines = diff.splitlines()
    assert len(diff_lines) >= 4
    assert diff_lines[0].startswith("--- ")
    assert diff_lines[1].startswith("+++ ")
    assert diff_lines[2].startswith("@@")
    assert "+++" not in diff_lines[0]
    assert "@@" not in diff_lines[0]

    # Step 4: Apply the exact generated diff via POST /api/apply-patch
    apply_payload = {
        "target_file": str(target_file),
        "patch_id": patch.get("patch_id", "patch_cand_01"),
        "patch_diff": diff,
    }
    apply_response = client.post("/api/apply-patch", json=apply_payload)
    assert apply_response.status_code == 200
    apply_data = apply_response.json()

    assert apply_data["success"] is True
    assert apply_data["target_file"] == str(target_file)
    assert apply_data["backup_file"] == str(target_file) + ".bak"

    # Step 5: Verify safety backup exists and contains original vulnerable code
    backup_path = Path(apply_data["backup_file"])
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET

    # Step 6: Verify file on disk has genuinely been updated
    on_disk_content = target_file.read_text(encoding="utf-8")
    assert on_disk_content != VULN_PYTHON_SNIPPET
    assert on_disk_content.strip() == remediated_code.strip()

    # Verify vulnerable f-string is eradicated
    assert 'f"SELECT id, role, email FROM accounts WHERE username = \'{username}\'"' not in on_disk_content

    # Verify parameterized placeholder and argument tuple are present
    assert ("%s" in on_disk_content or "?" in on_disk_content)
    assert ("cursor.execute(query, (" in on_disk_content or "cursor.execute(query, [" in on_disk_content)


def test_apply_patch_javascript_diff_roundtrip(tmp_path):
    """
    Verify complete patch generation and diff application roundtrip on JavaScript code.
    Ensures language neutrality and Tree-sitter validation for JS.
    """
    target_file = tmp_path / "search_service.js"
    target_file.write_text(VULN_JS_SNIPPET, encoding="utf-8")

    gen_payload = {
        "issue_id": "ISSUE-CWE89-JS-ROUNDTRIP",
        "target_file": str(target_file),
        "candidate_count": 3,
        "code_content": VULN_JS_SNIPPET,
    }
    gen_response = client.post("/api/generate-patches", json=gen_payload)
    assert gen_response.status_code == 200
    gen_data = gen_response.json()
    assert gen_data["verified_count"] >= 1

    patch = gen_data["verified_patches"][0]
    diff = patch["diff"]
    remediated_code = patch["remediated_code"]
    assert diff.startswith("--- ")
    assert "\n+++ " in diff
    assert "\n@@ " in diff

    apply_payload = {
        "target_file": str(target_file),
        "patch_id": patch.get("patch_id", "patch_cand_01"),
        "patch_diff": diff,
    }
    apply_response = client.post("/api/apply-patch", json=apply_payload)
    assert apply_response.status_code == 200
    assert apply_response.json()["success"] is True

    # Verify JavaScript file on disk is updated
    updated_js = target_file.read_text(encoding="utf-8")
    assert updated_js != VULN_JS_SNIPPET
    assert updated_js.strip() == remediated_code.strip()
    assert "LIKE '%${term}%'" not in updated_js


def test_apply_patch_malformed_diff_rejected(tmp_path):
    """
    Verify POST /api/apply-patch rejects invalid or malformed diffs with HTTP 422:
    - Case A: Arbitrary text without @@ hunk headers.
    - Case B: Corrupted hunk headers with unparseable line numbers.
    - Case C: Valid hunk format targeting non-matching context lines.
    - Case D: Diff that produces no changes (identical content).
    Asserts HTTP 422 is returned and disk file remains completely unaltered.
    """
    target_file = tmp_path / "app_safe_state.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    # Case A: Totally bogus string without hunks
    bogus_payload = {
        "target_file": str(target_file),
        "patch_id": "patch_bogus",
        "patch_diff": "BOGUS DIFF TEXT WITH NO HUNK HEADERS OR VALID FORMAT",
    }
    response_bogus = client.post("/api/apply-patch", json=bogus_payload)
    assert response_bogus.status_code == 422
    assert "detail" in response_bogus.json()
    assert target_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET

    # Case B: Corrupted hunk header
    corrupt_payload = {
        "target_file": str(target_file),
        "patch_id": "patch_corrupt",
        "patch_diff": "--- a/app.py\n+++ b/app.py\n@@ -invalid,line @@\n-some line\n+new line\n",
    }
    response_corrupt = client.post("/api/apply-patch", json=corrupt_payload)
    assert response_corrupt.status_code == 422
    assert target_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET

    # Case C: Context mismatch diff
    mismatch_payload = {
        "target_file": str(target_file),
        "patch_id": "patch_mismatch",
        "patch_diff": (
            "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,3 @@\n"
            " def completely_different_function():\n"
            "-    completely_different_line()\n"
            "+    new_replacement_line()\n"
        ),
    }
    response_mismatch = client.post("/api/apply-patch", json=mismatch_payload)
    assert response_mismatch.status_code == 422
    assert target_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET

    # Case D: Diff producing no changes
    no_change_diff = (
        "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,3 @@\n"
        " def login_user(request):\n"
        "     username = request.args.get('username')\n"
        "     cursor = db.cursor()\n"
    )
    res_no_change = client.post(
        "/api/apply-patch",
        json={"target_file": str(target_file), "patch_diff": no_change_diff},
    )
    assert res_no_change.status_code == 422
    assert target_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET


def test_apply_patch_empty_payload_rejected(tmp_path):
    """
    Verify POST /api/apply-patch returns HTTP 400 when neither
    remediated_code nor patch_diff is provided.
    """
    target_file = tmp_path / "empty_target.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    response = client.post("/api/apply-patch", json={"target_file": str(target_file)})
    assert response.status_code == 400
    assert "Either remediated_code or patch_diff" in response.json()["detail"]
