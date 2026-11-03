"""
test_independent_verification.py
Independent verification script by reviewer_m1_fix_2.
Tests diff generation, apply_unified_diff parsing, disk mutation, error handling, and roundtrip.
"""

import difflib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

# Add codedee_server to sys.path
SERVER_ROOT = Path("codedee/codedee_server").resolve()
sys.path.insert(0, str(SERVER_ROOT))

from app.main import app
from app.api.patches import generate_diff
from app.api.apply import apply_unified_diff, HUNK_HEADER_RE
from fastapi.testclient import TestClient

client = TestClient(app)

def test_1_generate_diff_formatting():
    print("[1] Testing generate_diff formatting...")
    orig = "def foo():\n    print('hello')\n    return 1\n"
    patched = "def foo():\n    print('hello world')\n    return 2\n"
    diff = generate_diff(orig, patched, "sample.py")
    
    assert diff.startswith("--- a/sample.py\n"), f"Expected header line with newline, got: {repr(diff[:30])}"
    assert "+++ b/sample.py\n" in diff, f"Expected +++ header line with newline, got: {repr(diff[:60])}"
    assert "\n@@ " in diff, f"Expected hunk header line preceded by newline, got: {repr(diff[:100])}"
    
    # Check that each line in diff ends with newline
    lines = diff.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        assert line.endswith("\n"), f"Line {idx} does not end with newline: {repr(line)}"
        
    # Check that headers are not fused
    assert not diff.startswith("--- a/sample.py+++"), "Headers are fused!"
    assert "@@ def foo():" not in lines[0], "Hunk header fused into file header!"
    print(" -> PASSED: Clean header separation and standard POSIX newlines verified.")

def test_2_apply_unified_diff_hunks_and_mutation():
    print("[2] Testing apply_unified_diff logic directly...")
    
    orig = "line1\nline2\nline3\nline4\nline5\n"
    diff = (
        "--- a/file.txt\n"
        "+++ b/file.txt\n"
        "@@ -2,3 +2,3 @@\n"
        " line2\n"
        "-line3\n"
        "+line3_modified\n"
        " line4\n"
    )
    result = apply_unified_diff(orig, diff)
    expected = "line1\nline2\nline3_modified\nline4\nline5\n"
    assert result == expected, f"Expected:\n{expected}\nGot:\n{result}"
    
    # Test multi-hunk diff
    multi_diff = (
        "--- a/file.txt\n"
        "+++ b/file.txt\n"
        "@@ -1,2 +1,2 @@\n"
        "-line1\n"
        "+line1_new\n"
        " line2\n"
        "@@ -4,2 +4,2 @@\n"
        " line4\n"
        "-line5\n"
        "+line5_new\n"
    )
    multi_result = apply_unified_diff(orig, multi_diff)
    expected_multi = "line1_new\nline2\nline3\nline4\nline5_new\n"
    assert multi_result == expected_multi, f"Multi-hunk failed: {multi_result}"
    
    # Test single-line format @@ -1 +1 @@
    single_diff = (
        "--- a/file.txt\n"
        "+++ b/file.txt\n"
        "@@ -1 +1 @@\n"
        "-line1\n"
        "+line1_replaced\n"
    )
    single_result = apply_unified_diff(orig, single_diff)
    assert single_result.startswith("line1_replaced\nline2\n")
    
    print(" -> PASSED: Single and multi-hunk diff application works correctly.")

def test_3_apply_unified_diff_error_rejections():
    print("[3] Testing apply_unified_diff rejection on invalid inputs...")
    
    orig = "line1\nline2\nline3\n"
    
    # Empty diff
    try:
        apply_unified_diff(orig, "")
        assert False, "Should have raised ValueError on empty diff"
    except ValueError as e:
        assert "empty" in str(e).lower()
        
    # Corrupt hunk header
    corrupt_header = "--- a/f\n+++ b/f\n@@ corrupt @@\n-line1\n+line1\n"
    try:
        apply_unified_diff(orig, corrupt_header)
        assert False, "Should have raised ValueError on corrupt hunk header"
    except ValueError as e:
        assert "malformed hunk header" in str(e).lower()
        
    # Context mismatch
    mismatch_diff = (
        "--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n"
        " line_WRONG\n"
        "-line2\n"
        "+line2_new\n"
    )
    try:
        apply_unified_diff(orig, mismatch_diff)
        assert False, "Should have raised ValueError on context mismatch"
    except ValueError as e:
        assert "context mismatch" in str(e).lower()
        
    # Deletion mismatch
    del_mismatch_diff = (
        "--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n"
        " line1\n"
        "-line_WRONG_DELETION\n"
        "+line2_new\n"
    )
    try:
        apply_unified_diff(orig, del_mismatch_diff)
        assert False, "Should have raised ValueError on deletion mismatch"
    except ValueError as e:
        assert "deletion mismatch" in str(e).lower()
        
    print(" -> PASSED: Correctly raises ValueError on malformed diffs and context/deletion mismatches.")

def test_4_live_roundtrip_generate_and_apply():
    print("[4] Testing live roundtrip: POST /api/generate-patches -> POST /api/apply-patch...")
    
    vuln_code = (
        "import sqlite3\n"
        "from flask import request\n\n"
        "def get_user_profile():\n"
        "    uid = request.args.get('uid')\n"
        "    query = f\"SELECT id, name, email FROM users WHERE id = {uid}\"\n"
        "    cursor = sqlite3.connect('app.db').cursor()\n"
        "    return cursor.execute(query).fetchall()\n"
    )
    
    with tempfile.TemporaryDirectory() as td:
        target_file = Path(td) / "profile.py"
        target_file.write_text(vuln_code, encoding="utf-8")
        
        # 1. Generate patches
        gen_payload = {
            "issue_id": "PROFILE-SQLI-001",
            "target_file": str(target_file),
            "code_content": vuln_code,
            "candidate_count": 3,
        }
        res_gen = client.post("/api/generate-patches", json=gen_payload)
        assert res_gen.status_code == 200, f"Generate failed: {res_gen.text}"
        data_gen = res_gen.json()
        assert data_gen["verified_count"] >= 1
        
        patch = data_gen["verified_patches"][0]
        diff = patch["diff"]
        remediated_code = patch["remediated_code"]
        
        # Verify diff headers
        diff_lines = diff.splitlines()
        assert diff_lines[0].startswith("--- a/")
        assert diff_lines[1].startswith("+++ b/")
        assert diff_lines[2].startswith("@@")
        
        # 2. Apply patch using patch_diff
        apply_payload = {
            "target_file": str(target_file),
            "patch_id": patch["patch_id"],
            "patch_diff": diff,
        }
        res_apply = client.post("/api/apply-patch", json=apply_payload)
        assert res_apply.status_code == 200, f"Apply failed: {res_apply.text}"
        data_apply = res_apply.json()
        assert data_apply["success"] is True
        
        # 3. Verify disk file is actually modified
        disk_content = target_file.read_text(encoding="utf-8")
        assert disk_content != vuln_code, "Target file was NOT mutated on disk!"
        assert disk_content.strip() == remediated_code.strip(), "Disk content doesn't match remediated code!"
        assert 'f"SELECT id, name, email FROM users WHERE id = {uid}"' not in disk_content, "Vulnerable f-string still exists!"
        
        # 4. Verify backup file exists and contains original code
        backup_file = target_file.with_name("profile.py.bak")
        assert backup_file.exists(), "Backup file not found!"
        assert backup_file.read_text(encoding="utf-8") == vuln_code, "Backup file corrupted!"
        
        # 5. Verify no-op diff returns HTTP 422
        no_op_diff = (
            "--- a/profile.py\n"
            "+++ b/profile.py\n"
            "@@ -1,3 +1,3 @@\n"
            " import sqlite3\n"
            " from flask import request\n"
            " \n"
        )
        res_noop = client.post("/api/apply-patch", json={"target_file": str(target_file), "patch_diff": no_op_diff})
        assert res_noop.status_code == 422, f"Expected 422 for no-op diff, got: {res_noop.status_code}"
        assert "no changes" in res_noop.json()["detail"].lower()
        
        # 6. Verify malformed diff returns HTTP 422 and leaves file unchanged
        current_content = target_file.read_text(encoding="utf-8")
        res_bad = client.post("/api/apply-patch", json={"target_file": str(target_file), "patch_diff": "INVALID JUNK DIFF"})
        assert res_bad.status_code == 422, f"Expected 422 for malformed diff, got: {res_bad.status_code}"
        assert target_file.read_text(encoding="utf-8") == current_content, "File altered after failed diff!"
        
    print(" -> PASSED: Live roundtrip, disk mutation, backup creation, and 422 rejections verified.")

if __name__ == "__main__":
    test_1_generate_diff_formatting()
    test_2_apply_unified_diff_hunks_and_mutation()
    test_3_apply_unified_diff_error_rejections()
    test_4_live_roundtrip_generate_and_apply()
    print("\nALL INDEPENDENT VERIFICATION TESTS PASSED SUCCESSFULLY!")
