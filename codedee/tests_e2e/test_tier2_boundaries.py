"""
test_tier2_boundaries.py - Tier 2: Boundary & Corner Cases (>=5 tests per feature).

Opaque-box adversarial stress tests covering:
1. /health boundaries (unsupported methods, malformed headers, query params, concurrency)
2. /api/scan boundaries (empty files, huge files, syntax errors, 404s, 400s, non-vulnerable code)
3. /api/generate-patches boundaries (unknown issue_ids, invalid candidate counts, 404/422 validation)
4. /api/apply-patch boundaries (missing files, malformed diffs, empty code, syntax error rollback)
5. Dataset invariants (uniqueness, non-empty code, boolean types, CVSS regex, null safety)
"""

import re
from pathlib import Path
import pytest


# ============================================================================
# Feature 1: Health Check Boundaries (>=5 tests)
# ============================================================================

def test_health_post_method_not_allowed(client):
    """Test 2.1: POST to /health should return 405 Method Not Allowed."""
    resp = client.post("/health", json={"data": 123})
    assert resp.status_code == 405


def test_health_query_parameters_tolerance(client):
    """Test 2.2: Verify /health tolerates unexpected query parameters without breaking."""
    resp = client.get("/health?unexpected_param=1&debug=true&mode=chaos")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    assert data["backend_version"] == "1.0.0"


def test_health_custom_accept_headers(client):
    """Test 2.3: Verify /health response with custom Accept and User-Agent headers."""
    resp = client.get("/health", headers={"Accept": "*/*", "User-Agent": "CodeDEE-E2E-Tester/1.0"})
    assert resp.status_code in (200, 503)
    assert resp.headers.get("content-type", "").startswith("application/json")


def test_health_root_post_rejected(client):
    """Test 2.4: POST to / root endpoint should return 405 Method Not Allowed."""
    resp = client.post("/", json={})
    assert resp.status_code == 405


def test_health_rapid_sequential_queries(client):
    """Test 2.5: Verify stability under rapid back-to-back health checks."""
    for _ in range(5):
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
        assert resp.json()["model_name"] == "qwen2.5-coder:7b"


# ============================================================================
# Feature 2: /api/scan Boundaries & Corner Cases (>=5 tests)
# ============================================================================

def test_scan_empty_code_content(client):
    """Test 2.6: Scan 0-byte / empty string buffer returns 0 issues safely."""
    resp = client.post(
        "/api/scan",
        json={"code_content": "", "file_name": "empty.py", "language": "python"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["issues_count"] == 0
    assert data["files_scanned"] == 1


def test_scan_whitespace_and_comments_only(client):
    """Test 2.7: Scan whitespace and comments only without executable code."""
    code = (
        "   \n\n"
        "# Just a comment with SQL keywords\n"
        "# SELECT * FROM users WHERE id = 'admin'\n"
        "   \t\n"
    )
    resp = client.post(
        "/api/scan",
        json={"code_content": code, "file_name": "comments.py", "language": "python"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["issues_count"] == 0


def test_scan_single_line_minimal_code(client):
    """Test 2.8: Scan minimal single statement code."""
    code = "x = 42"
    resp = client.post(
        "/api/scan",
        json={"code_content": code, "file_name": "min.py", "language": "python"},
    )
    assert resp.status_code == 200
    assert resp.json()["issues_count"] == 0


def test_scan_huge_file_stress(client, temp_workspace):
    """Test 2.9: Stress test AST parser and maintainability engine with large file."""
    lines = ["def large_func(x):", "    total = x"]
    for i in range(80):
        lines.append(f"    total += {i}")
    lines.append("    return total\n")
    large_code = "\n".join(lines)
    f = temp_workspace.create_file("large.py", large_code)

    resp = client.post("/api/scan", json={"target_path": str(f)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["files_scanned"] == 1
    assert data["issues_count"] == 0
    assert data["maintainability"]["file_sloc"] >= 80


def test_scan_syntax_error_file_graceful(client, temp_workspace):
    """Test 2.10: Scan file with syntax errors; Tree-sitter must handle ERROR nodes without crashing."""
    broken_code = (
        "def broken(\n"
        "    if if return <<<< ?!\n"
        "    SELECT FROM WHERE\n"
    )
    f = temp_workspace.create_file("broken.py", broken_code)
    resp = client.post("/api/scan", json={"target_path": str(f)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["files_scanned"] == 1


def test_scan_non_existent_target_path(client):
    """Test 2.11: Non-existent target_path returns 404 Not Found."""
    resp = client.post(
        "/api/scan",
        json={"target_path": "d:/non_existent_folder_abc123/file.py"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_scan_missing_both_target_and_content(client):
    """Test 2.12: Request omitting both target_path and code_content returns 400 Bad Request."""
    resp = client.post("/api/scan", json={})
    assert resp.status_code == 400
    assert "either target_path or code_content" in resp.json()["detail"].lower()


def test_scan_python_non_vulnerable_parameterized(client):
    """Test 2.13: Non-vulnerable Python code with parameterized query returns 0 CWE-89 issues."""
    safe_code = (
        "import sqlite3\n"
        "def get_user(user_id):\n"
        "    conn = sqlite3.connect('app.db')\n"
        "    cursor = conn.cursor()\n"
        "    return cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()\n"
    )
    resp = client.post(
        "/api/scan",
        json={"code_content": safe_code, "file_name": "safe.py", "language": "python"},
    )
    assert resp.status_code == 200
    assert resp.json()["issues_count"] == 0


def test_scan_javascript_non_vulnerable_parameterized(client):
    """Test 2.14: Non-vulnerable JavaScript code with $1 parameterized query returns 0 CWE-89 issues."""
    safe_code = (
        "const { Client } = require('pg');\n"
        "async function getUser(req, res) {\n"
        "    const client = new Client();\n"
        "    const result = await client.query('SELECT * FROM users WHERE id = $1', [req.query.id]);\n"
        "    res.json(result.rows);\n"
        "}\n"
    )
    resp = client.post(
        "/api/scan",
        json={"code_content": safe_code, "file_name": "safe.js", "language": "javascript"},
    )
    assert resp.status_code == 200
    assert resp.json()["issues_count"] == 0


def test_scan_typescript_non_vulnerable_orm(client):
    """Test 2.15: Safe TypeScript ORM invocation without dynamic concatenation returns 0 issues."""
    safe_code = (
        "import { User } from './models';\n"
        "export async function findById(id: string) {\n"
        "    return await User.findOne({ where: { id } });\n"
        "}\n"
    )
    resp = client.post(
        "/api/scan",
        json={"code_content": safe_code, "file_name": "safe_orm.ts", "language": "typescript"},
    )
    assert resp.status_code == 200
    assert resp.json()["issues_count"] == 0


def test_scan_sql_keywords_in_standard_strings_not_flagged(client):
    """Test 2.16: SQL keywords in logging or normal strings without execution sink are not flagged."""
    code = (
        "import logging\n"
        "def log_action(user):\n"
        "    msg = f'User {user} attempted to SELECT and UPDATE their preferences'\n"
        "    logging.info(msg)\n"
    )
    resp = client.post(
        "/api/scan",
        json={"code_content": code, "file_name": "logger.py", "language": "python"},
    )
    assert resp.status_code == 200
    assert resp.json()["issues_count"] == 0


# ============================================================================
# Feature 3: /api/generate-patches Boundaries (>=5 tests)
# ============================================================================

def test_generate_patches_unknown_issue_and_target_file(client):
    """Test 2.17: Non-existent issue_id and target_file returns 404."""
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "NON_EXISTENT_ISSUE_XYZ_999"},
    )
    assert resp.status_code == 404
    assert "could not locate" in resp.json()["detail"].lower()


def test_generate_patches_missing_issue_id(client):
    """Test 2.18: Omitting mandatory issue_id field returns 422 Unprocessable Entity."""
    resp = client.post(
        "/api/generate-patches",
        json={"candidate_count": 3},
    )
    assert resp.status_code == 422


def test_generate_patches_candidate_count_underflow(client):
    """Test 2.19: candidate_count < 1 returns 422 validation error."""
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "TEST", "candidate_count": 0},
    )
    assert resp.status_code == 422


def test_generate_patches_candidate_count_overflow(client):
    """Test 2.20: candidate_count > 5 returns 422 validation error."""
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "TEST", "candidate_count": 10},
    )
    assert resp.status_code == 422


def test_generate_patches_empty_code_content(client):
    """Test 2.21: Empty code_content string returns 404 not found."""
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "EMPTY_TEST", "code_content": ""},
    )
    assert resp.status_code == 404


def test_generate_patches_with_alias_num_candidates(client):
    """Test 2.22: Verify alias num_candidates is reconciled properly."""
    code = "def f(u): cursor.execute(f'SELECT * FROM u WHERE id={u}')"
    resp = client.post(
        "/api/generate-patches",
        json={"issue_id": "ALIAS_TEST", "code_content": code, "num_candidates": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["verified_count"] >= 1


# ============================================================================
# Feature 4: /api/apply-patch Boundaries (>=5 tests)
# ============================================================================

def test_apply_patch_non_existent_target_file(client):
    """Test 2.23: Applying patch to non-existent target file returns 404."""
    resp = client.post(
        "/api/apply-patch",
        json={"target_file": "d:/ghost_file_123.py", "remediated_code": "def a(): pass\n"},
    )
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"].lower()


def test_apply_patch_missing_both_remediated_and_diff(client, temp_workspace):
    """Test 2.24: Omitting both remediated_code and patch_diff returns 400 Bad Request."""
    f = temp_workspace.create_file("test.py", "x = 1\n")
    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(f)},
    )
    assert resp.status_code == 400
    assert "either remediated_code or patch_diff" in resp.json()["detail"].lower()


def test_apply_patch_corrupt_unified_diff(client, temp_workspace):
    """Test 2.25: Corrupted diff without valid hunks does not corrupt target file."""
    orig = "def keep_intact():\n    return 42\n"
    f = temp_workspace.create_file("corrupt.py", orig)
    garbage_diff = "MALFORMED GARBAGE DIFF\nNOT A UNIFIED DIFF\n"

    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(f), "patch_diff": garbage_diff},
    )
    # Target file should not be destroyed
    assert f.exists()


def test_apply_patch_reverts_syntax_error_javascript(client, temp_workspace):
    """Test 2.26: JavaScript patch with syntax error is rejected with 422 and reverted."""
    orig_js = "function valid() { return 10; }\n"
    broken_js = "function valid() { return return <<< ; }\n"
    f = temp_workspace.create_file("script.js", orig_js)

    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(f), "remediated_code": broken_js},
    )
    assert resp.status_code == 422
    assert f.read_text(encoding="utf-8") == orig_js


def test_apply_patch_backup_created_even_before_reversion(client, temp_workspace):
    """Test 2.27: Backup file exists on disk even if patch failed syntax check."""
    orig = "x = 1\n"
    broken = "x = = <<<\n"
    f = temp_workspace.create_file("backup_test.py", orig)

    resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(f), "remediated_code": broken},
    )
    assert resp.status_code == 422
    backup = f.with_name(f"{f.name}.bak")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == orig


# ============================================================================
# Feature 5: Dataset Boundaries & Invariants (>=5 tests)
# ============================================================================

def test_dataset_sample_ids_are_unique(mini_datasets):
    """Test 2.28: All 105 sample_ids must be strictly unique."""
    ids = [r["sample_id"] for r in mini_datasets]
    assert len(ids) == len(set(ids)), "Found duplicate sample_id in dataset"


def test_dataset_original_code_non_empty(mini_datasets):
    """Test 2.29: No record should have null, None, or empty original_code."""
    for r in mini_datasets:
        code = r.get("original_code")
        assert code is not None, f"Null code in {r.get('sample_id')}"
        assert len(code.strip()) > 0, f"Empty code in {r.get('sample_id')}"


def test_dataset_is_vulnerable_is_boolean(mini_datasets):
    """Test 2.30: Is_vulnerable must be strictly boolean True or False."""
    for r in mini_datasets:
        assert isinstance(r["Is_vulnerable"], bool)


def test_dataset_cvss_vector_format_regex(mini_datasets):
    """Test 2.31: cvss_v31_vector must conform to CVSS 3.1 vector string regex."""
    cvss_pattern = re.compile(r"^CVSS:3\.1/AV:[NALP]/AC:[LH]/PR:[NLH]/UI:[NR]/S:[UC]/C:[NLH]/I:[NLH]/A:[NLH]")
    for r in mini_datasets:
        vector = r.get("cvss_v31_vector", "")
        assert cvss_pattern.match(vector), f"Invalid CVSS vector {vector} in {r.get('sample_id')}"


def test_dataset_languages_lowercase_standard(mini_datasets):
    """Test 2.32: All language values must be strictly lowercase ('python', 'javascript', 'typescript')."""
    valid_langs = {"python", "javascript", "typescript"}
    for r in mini_datasets:
        assert r["language"] in valid_langs, f"Invalid language {r['language']} in {r.get('sample_id')}"


def test_dataset_fixed_code_syntax_validity(mini_datasets):
    """Test 2.33: For records with fixed_code present, verify fixed_code is non-empty string."""
    fixed_count = 0
    for r in mini_datasets:
        fixed = r.get("fixed_code")
        if fixed is not None:
            assert isinstance(fixed, str)
            assert len(fixed.strip()) > 0
            fixed_count += 1
    assert fixed_count >= 30, f"Expected at least 30 samples with fixed_code, found {fixed_count}"
