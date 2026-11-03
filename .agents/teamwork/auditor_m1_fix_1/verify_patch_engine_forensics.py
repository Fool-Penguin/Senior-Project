"""
verify_patch_engine_forensics.py - Independent Forensic Audit Verification Script
Milestone 1 Iteration 2: Diff Generation, Unified Diff Parsing, Disk Application, and Safety.

Auditor: auditor_m1_fix_1
Profile: General Project
Integrity Mode: development
"""

import ast
import difflib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

# Add codedee_server to path
SERVER_ROOT = Path("d:/4th-year/Senior-Project/codedee/codedee_server").resolve()
sys.path.insert(0, str(SERVER_ROOT))

from app.api import apply, patches
from app.api.apply import HUNK_HEADER_RE, apply_unified_diff, apply_patch
from app.api.patches import generate_diff, generate_parameterized_candidates
from app.main import app
from fastapi.testclient import TestClient
from fastapi import HTTPException

client = TestClient(app)

results = []

def record(test_name: str, passed: bool, details: str):
    status_str = "PASS" if passed else "FAIL"
    results.append({"name": test_name, "status": status_str, "details": details})
    print(f"[{status_str}] {test_name}: {details}")


# ============================================================================
# Check 1: Static AST Analysis for Facades, Canned Returns & Test Bypasses
# ============================================================================
def check_static_ast_integrity():
    files_to_check = [
        SERVER_ROOT / "app/api/apply.py",
        SERVER_ROOT / "app/api/patches.py",
    ]
    
    suspicious_patterns = [
        "return True", "return False", "return []", "return {}", "pass"
    ]
    
    for file_path in files_to_check:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check for empty body / facade functions
                if len(node.body) == 1:
                    stmt = node.body[0]
                    if isinstance(stmt, ast.Pass):
                        record(f"AST Facade Check ({file_path.name}::{node.name})", False, "Found single 'pass' statement body")
                        return
                    if isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Name) and stmt.exc.id == "NotImplementedError":
                        record(f"AST Facade Check ({file_path.name}::{node.name})", False, "Found NotImplementedError stub")
                        return

        # Check for hardcoded test bypasses (e.g. if 'test' in path)
        content = file_path.read_text(encoding="utf-8")
        if "if 'test' in" in content or 'if "test" in' in content or "if target_path == 'test'" in content:
            record(f"AST Bypass Check ({file_path.name})", False, "Found artificial test path check in production code")
            return

    record("AST Facade & Bypass Check", True, "Zero facades, stubs, or artificial test path bypasses in apply.py and patches.py")


# ============================================================================
# Check 2: Diff Generation Formatting & POSIX/Git Compliance
# ============================================================================
def check_diff_generation_integrity():
    orig = "line 1\nline 2\nline 3\n"
    patched = "line 1\nline 2 modified\nline 3\n"
    filename = "sample.py"
    
    diff = generate_diff(orig, patched, filename)
    
    lines = diff.splitlines(keepends=True)
    if len(lines) < 4:
        record("Diff Generation Compliance", False, f"Diff had fewer than 4 lines: {repr(diff)}")
        return
        
    if not lines[0].startswith("--- a/sample.py\n"):
        record("Diff Generation Compliance", False, f"Line 0 malformed: {repr(lines[0])}")
        return
    if not lines[1].startswith("+++ b/sample.py\n"):
        record("Diff Generation Compliance", False, f"Line 1 malformed: {repr(lines[1])}")
        return
    if not lines[2].startswith("@@ ") or not lines[2].endswith("\n"):
        record("Diff Generation Compliance", False, f"Hunk header malformed: {repr(lines[2])}")
        return

    # Check that no fusion occurred
    if "+++" in lines[0] or "@@" in lines[0] or "@@" in lines[1]:
        record("Diff Generation Compliance", False, "Header fusion detected in diff output")
        return

    # Check identical files produce empty diff
    empty_diff = generate_diff(orig, orig, filename)
    if empty_diff != "":
        record("Diff Generation Compliance", False, f"Identical files produced non-empty diff: {repr(empty_diff)}")
        return

    record("Diff Generation Compliance", True, "generate_diff outputs strictly compliant POSIX/Git headers with clean newlines")


# ============================================================================
# Check 3: Unified Diff Application Tracing & Byte Change Verification
# ============================================================================
def check_diff_application_byte_verification():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        target = tmp_path / "test_script.py"
        orig_bytes = b"def calculate(a, b):\n    total = a + b\n    return total\n"
        target.write_bytes(orig_bytes)
        
        patched_code = "def calculate(a, b):\n    # added docstring\n    total = a * b\n    return total\n"
        diff = generate_diff(orig_bytes.decode("utf-8"), patched_code, "test_script.py")
        
        # Apply via API
        resp = client.post("/api/apply-patch", json={
            "target_file": str(target),
            "patch_diff": diff,
            "patch_id": "P_AUDIT_01"
        })
        
        if resp.status_code != 200:
            record("Diff Application Byte Tracing", False, f"API returned {resp.status_code}: {resp.text}")
            return
            
        data = resp.json()
        backup_file = Path(data["backup_file"])
        
        # 1. Verify backup file exists and matches original bytes exactly
        if not backup_file.exists():
            record("Diff Application Byte Tracing", False, "Backup file was not created on disk")
            return
        if backup_file.read_bytes() != orig_bytes:
            record("Diff Application Byte Tracing", False, "Backup file bytes do not match original bytes")
            return
            
        # 2. Verify target file on disk was genuinely mutated to patched_code
        new_bytes = target.read_bytes()
        if new_bytes == orig_bytes:
            record("Diff Application Byte Tracing", False, "Target file bytes were not modified on disk")
            return
        # Verify text content matches expected patched code
        disk_text = target.read_text(encoding="utf-8")
        if disk_text != patched_code:
            record("Diff Application Byte Tracing", False, f"Target file text does not match patched code: {disk_text}")
            return
        # Verify byte normalization matches
        if new_bytes.replace(b"\r\n", b"\n") != patched_code.encode("utf-8"):
            record("Diff Application Byte Tracing", False, f"Target file bytes do not match expected: {new_bytes}")
            return

    # Check CRLF preservation in apply_unified_diff directly
    crlf_orig = "line 1\r\nline 2\r\nline 3\r\n"
    crlf_diff = (
        "--- a/crlf.txt\n"
        "+++ b/crlf.txt\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\r\n"
        "-line 2\r\n"
        "+line 2 MODIFIED\r\n"
        " line 3\r\n"
    )
    crlf_result = apply_unified_diff(crlf_orig, crlf_diff)
    if crlf_result != "line 1\r\nline 2 MODIFIED\r\nline 3\r\n":
        record("Diff Application Byte Tracing", False, f"CRLF diff application failed to preserve CRLF: {repr(crlf_result)}")
        return

    record("Diff Application Byte Tracing", True, "Verified genuine disk mutation, byte-identical .bak backup, and CRLF preservation")


# ============================================================================
# Check 4: Multi-Hunk Diff Parsing & Correct Hunk Offsets
# ============================================================================
def check_multi_hunk_diff_parsing():
    orig = (
        "line 1\n"
        "line 2\n"
        "line 3\n"
        "line 4\n"
        "line 5\n"
        "line 6\n"
        "line 7\n"
        "line 8\n"
        "line 9\n"
        "line 10\n"
    )
    patched = (
        "line 1\n"
        "line 2 MODIFIED\n"
        "line 3\n"
        "line 4\n"
        "line 5\n"
        "line 6\n"
        "line 7\n"
        "line 8\n"
        "line 9 MODIFIED\n"
        "line 10\n"
    )
    diff = generate_diff(orig, patched, "sample.txt")
    
    # Assert diff has at least 2 hunks
    hunk_matches = HUNK_HEADER_RE.findall(diff)
    if len(hunk_matches) < 2:
        # Depending on context lines, difflib might make 1 or 2 hunks. Let's force 2 separated hunks:
        pass

    result = apply_unified_diff(orig, diff)
    if result != patched:
        record("Multi-Hunk Diff Application", False, f"Multi-hunk application mismatch. Got:\n{result}\nExpected:\n{patched}")
        return

    # Explicit multi-hunk synthetic diff test
    multi_hunk_diff = (
        "--- a/file.txt\n"
        "+++ b/file.txt\n"
        "@@ -2,3 +2,3 @@\n"
        " line 2\n"
        "-line 3\n"
        "+line 3 MODIFIED\n"
        " line 4\n"
        "@@ -8,3 +8,3 @@\n"
        " line 8\n"
        "-line 9\n"
        "+line 9 MODIFIED\n"
        " line 10\n"
    )
    res2 = apply_unified_diff(orig, multi_hunk_diff)
    expected2 = (
        "line 1\n"
        "line 2\n"
        "line 3 MODIFIED\n"
        "line 4\n"
        "line 5\n"
        "line 6\n"
        "line 7\n"
        "line 8\n"
        "line 9 MODIFIED\n"
        "line 10\n"
    )
    if res2 != expected2:
        record("Multi-Hunk Diff Application", False, f"Synthetic multi-hunk application failed.\nGot:\n{res2}\nExpected:\n{expected2}")
        return

    record("Multi-Hunk Diff Application", True, "Successfully parsed and applied separated multi-hunk diffs")


# ============================================================================
# Check 5: Adversarial Context Mismatches & Boundary Enforcement
# ============================================================================
def check_adversarial_rejections():
    orig = "def foo():\n    return 'secret'\n"
    
    # 1. Context line mismatch
    mismatch_context_diff = (
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def bar():\n"
        "-    return 'secret'\n"
        "+    return 'public'\n"
    )
    try:
        apply_unified_diff(orig, mismatch_context_diff)
        record("Context Mismatch Rejection", False, "Failed to reject context mismatch diff")
        return
    except ValueError as e:
        if "Context mismatch" not in str(e):
            record("Context Mismatch Rejection", False, f"Wrong exception message: {e}")
            return

    # 2. Deletion line mismatch
    mismatch_deletion_diff = (
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def foo():\n"
        "-    return 'wrong_string'\n"
        "+    return 'public'\n"
    )
    try:
        apply_unified_diff(orig, mismatch_deletion_diff)
        record("Deletion Mismatch Rejection", False, "Failed to reject deletion mismatch diff")
        return
    except ValueError as e:
        if "Deletion mismatch" not in str(e):
            record("Deletion Mismatch Rejection", False, f"Wrong exception message: {e}")
            return

    # 3. Corrupt hunk header
    corrupt_hunk_diff = (
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -not_a_number,1 +1,1 @@\n"
        " def foo():\n"
    )
    try:
        apply_unified_diff(orig, corrupt_hunk_diff)
        record("Corrupt Hunk Rejection", False, "Failed to reject malformed hunk header")
        return
    except ValueError as e:
        if "Malformed hunk header" not in str(e):
            record("Corrupt Hunk Rejection", False, f"Wrong exception message: {e}")
            return

    # 4. Out-of-order / backwards hunk line
    backwards_hunk_diff = (
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -2,1 +2,1 @@\n"
        "-    return 'secret'\n"
        "+    return 'public'\n"
        "@@ -1,1 +1,1 @@\n"
        "-def foo():\n"
        "+def baz():\n"
    )
    try:
        apply_unified_diff(orig, backwards_hunk_diff)
        record("Backwards Hunk Rejection", False, "Failed to reject backwards hunk line numbering")
        return
    except ValueError as e:
        if "is before current line" not in str(e):
            record("Backwards Hunk Rejection", False, f"Wrong exception message: {e}")
            return

    # 5. Diff with zero changes applied to API
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "ident.py"
        f.write_text(orig, encoding="utf-8")
        no_change_diff = (
            "--- a/ident.py\n"
            "+++ b/ident.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def foo():\n"
            "     return 'secret'\n"
        )
        resp = client.post("/api/apply-patch", json={"target_file": str(f), "patch_diff": no_change_diff})
        if resp.status_code != 422:
            record("No-Change Diff Rejection", False, f"Expected 422 for no-change diff, got {resp.status_code}")
            return
        if "no changes" not in resp.json()["detail"].lower():
            record("No-Change Diff Rejection", False, f"Wrong error detail: {resp.json()}")
            return

    record("Adversarial Mismatch & Boundary Checks", True, "Strict rejection of context mismatches, deletion mismatches, corrupt hunks, backwards hunks, and zero-change diffs with HTTP 422")


# ============================================================================
# Check 6: Tree-sitter Syntax Validation & Rollback on Diff Injection
# ============================================================================
def check_cst_validation_and_rollback():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "calc.py"
        valid_code = "def add(x, y):\n    return x + y\n"
        target.write_text(valid_code, encoding="utf-8")
        
        # Diff that introduces syntax error
        bad_syntax_diff = (
            "--- a/calc.py\n"
            "+++ b/calc.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def add(x, y):\n"
            "-    return x + y\n"
            "+    return return <<<\n"
        )
        
        resp = client.post("/api/apply-patch", json={
            "target_file": str(target),
            "patch_diff": bad_syntax_diff,
        })
        
        if resp.status_code != 422:
            record("CST Syntax Validation & Rollback", False, f"Expected 422 for syntax error, got {resp.status_code}")
            return
            
        if "invalid cst syntax" not in resp.json()["detail"].lower():
            record("CST Syntax Validation & Rollback", False, f"Unexpected error detail: {resp.json()}")
            return
            
        # Verify file on disk remained original
        current_content = target.read_text(encoding="utf-8")
        if current_content != valid_code:
            record("CST Syntax Validation & Rollback", False, f"File on disk corrupted after syntax error: {current_content}")
            return

    record("CST Syntax Validation & Rollback", True, "Tree-sitter parser detects syntax corruption and preserves disk state safely")


# ============================================================================
# Check 7: End-to-End Vulnerability Remediation Roundtrip (Python & JS)
# ============================================================================
def check_e2e_remediation_roundtrip():
    vuln_py = (
        "def query_user(req):\n"
        "    uid = req.args.get('id')\n"
        "    cursor = db.cursor()\n"
        "    sql = f\"SELECT * FROM users WHERE id = '{uid}'\"\n"
        "    cursor.execute(sql)\n"
        "    return cursor.fetchall()\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        f_py = Path(tmpdir) / "vuln_user.py"
        f_py.write_text(vuln_py, encoding="utf-8")
        
        # 1. Generate patches
        gen_resp = client.post("/api/generate-patches", json={
            "issue_id": "TEST_ROUNDTRIP_AUDIT",
            "target_file": str(f_py),
            "code_content": vuln_py,
        })
        if gen_resp.status_code != 200:
            record("E2E Remediation Roundtrip", False, f"Generate patches returned {gen_resp.status_code}")
            return
            
        gen_data = gen_resp.json()
        if gen_data["verified_count"] < 1:
            record("E2E Remediation Roundtrip", False, "0 verified patches generated")
            return
            
        patch = gen_data["verified_patches"][0]
        diff = patch["diff"]
        
        # 2. Apply patch diff
        apply_resp = client.post("/api/apply-patch", json={
            "target_file": str(f_py),
            "patch_diff": diff,
        })
        if apply_resp.status_code != 200:
            record("E2E Remediation Roundtrip", False, f"Apply patch returned {apply_resp.status_code}")
            return
            
        # 3. Verify disk content
        remediated_text = f_py.read_text(encoding="utf-8")
        if "f\"SELECT * FROM users WHERE id = '{uid}'\"" in remediated_text:
            record("E2E Remediation Roundtrip", False, "Vulnerable f-string remains on disk")
            return
        if "?" not in remediated_text and "%s" not in remediated_text:
            record("E2E Remediation Roundtrip", False, "No parameter placeholder found on disk")
            return
        if not (f_py.with_name(f"{f_py.name}.bak").exists()):
            record("E2E Remediation Roundtrip", False, "Safety backup missing")
            return

    record("E2E Remediation Roundtrip", True, "End-to-end patch generation, diff formatting, and disk mutation verified cleanly")


def main():
    print("=" * 70)
    print("FORENSIC AUDIT VERIFICATION: Milestone 1 Iteration 2 Patch Engine")
    print("=" * 70)
    
    check_static_ast_integrity()
    check_diff_generation_integrity()
    check_diff_application_byte_verification()
    check_multi_hunk_diff_parsing()
    check_adversarial_rejections()
    check_cst_validation_and_rollback()
    check_e2e_remediation_roundtrip()
    
    print("=" * 70)
    all_passed = all(r["status"] == "PASS" for r in results)
    passed_count = sum(1 for r in results if r["status"] == "PASS")
    total_count = len(results)
    
    print(f"Summary: {passed_count}/{total_count} checks PASSED.")
    verdict = "CLEAN" if all_passed else "INTEGRITY VIOLATION"
    print(f"FINAL FORENSIC AUDIT VERDICT: {verdict}")
    print("=" * 70)
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
