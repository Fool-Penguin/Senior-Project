"""
Prototype test script demonstrating the exact test cases recommended for test_api.py.
Tests against the live/current backend to demonstrate:
1. The roundtrip test currently fails because the diff is mangled and content on disk doesn't update.
2. The malformed diff test currently fails because the backend returns 200 instead of 422.
"""

import sys
from pathlib import Path
sys.path.insert(0, r"d:\4th-year\Senior-Project\codedee\codedee_server")

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

VULN_PYTHON_SNIPPET = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""

def test_roundtrip_prototype(tmp_path):
    target_file = tmp_path / "vulnerable_login.py"
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

    # Step 2: Extract verified patch and unified diff
    patch = gen_data["verified_patches"][0]
    diff = patch["diff"]
    assert isinstance(diff, str) and len(diff) > 0

    # Step 3: Check diff headers
    assert diff.startswith("--- "), f"Diff should start with '--- ', got: {diff[:50]}"
    assert "\n+++ " in diff, f"Diff header must have newline before '+++ ', got: {diff[:100]}"
    assert "\n@@ " in diff, f"Diff header must have newline before '@@ ', got: {diff[:100]}"

    # Step 4: Apply the diff
    apply_payload = {
        "target_file": str(target_file),
        "patch_id": patch.get("patch_id", "patch_cand_01"),
        "patch_diff": diff,
    }
    apply_response = client.post("/api/apply-patch", json=apply_payload)
    assert apply_response.status_code == 200
    apply_data = apply_response.json()
    assert apply_data["success"] is True

    # Step 5: Verify on disk
    on_disk_content = target_file.read_text(encoding="utf-8")
    assert on_disk_content != VULN_PYTHON_SNIPPET
    assert 'f"SELECT id, role, email FROM accounts WHERE username = \'{username}\'"' not in on_disk_content
    assert ("%s" in on_disk_content or "?" in on_disk_content)


def test_malformed_diff_prototype(tmp_path):
    target_file = tmp_path / "app_safe_state.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    bogus_payload = {
        "target_file": str(target_file),
        "patch_id": "patch_bogus",
        "patch_diff": "BOGUS DIFF TEXT WITH NO HUNK HEADERS OR VALID FORMAT",
    }
    response_bogus = client.post("/api/apply-patch", json=bogus_payload)
    assert response_bogus.status_code == 422
