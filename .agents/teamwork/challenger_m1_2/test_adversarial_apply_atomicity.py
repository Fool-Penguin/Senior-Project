"""
Adversarial Test Suite 1: File Application Atomicity & Rollback Verification.
Tests the /api/apply-patch endpoint for:
1. Syntax error rejection with automatic rollback and original file preservation.
2. Unified diff corruption and syntax breakage.
3. Multi-language atomicity (Python, JavaScript, TypeScript).
4. Backup (.bak) file integrity.
5. Missing file handling (404) and invalid request bodies (400/422).
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Add codedee_server to path
server_root = Path(r"d:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(server_root))

from app.main import app

client = TestClient(app)

def test_apply_valid_remediated_code():
    """Verify that a valid remediated patch succeeds and creates a backup."""
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8") as f:
        original = 'def vulnerable(x):\n    query = f"SELECT * FROM users WHERE id = {x}"\n    return query\n'
        f.write(original)
        f.flush()
        file_path = f.name

    try:
        remediated = 'def vulnerable(x):\n    query = "SELECT * FROM users WHERE id = %s"\n    return query, (x,)\n'
        resp = client.post("/api/apply-patch", json={
            "target_file": file_path,
            "remediated_code": remediated,
            "patch_id": "PATCH_TEST_001"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["success"] is True

        # Check content on disk
        updated = Path(file_path).read_text(encoding="utf-8")
        assert updated == remediated

        # Check backup file
        bak_file = Path(file_path + ".bak")
        assert bak_file.exists(), "Backup .bak file was not created"
        assert bak_file.read_text(encoding="utf-8") == original, "Backup content does not match original"
    finally:
        for p in [Path(file_path), Path(file_path + ".bak")]:
            if p.exists():
                p.unlink()

def test_apply_invalid_python_syntax_rollback():
    """Adversarial: Remediated code introduces Python syntax error."""
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8") as f:
        original = 'def hello(name):\n    print("Hello", name)\n'
        f.write(original)
        f.flush()
        file_path = f.name

    try:
        # Syntax error: unclosed paren and colon inside expression
        corrupted_code = 'def hello(name:\n    print("Broken" ++\n'
        resp = client.post("/api/apply-patch", json={
            "target_file": file_path,
            "remediated_code": corrupted_code,
            "patch_id": "BAD_PATCH_PY"
        })
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
        assert "invalid CST syntax" in resp.json()["detail"]

        # CRUCIAL: Original file must remain 100% intact!
        current = Path(file_path).read_text(encoding="utf-8")
        assert current == original, "Atomicity violation! Original file was modified despite syntax error"

        # Check backup file existence
        bak_file = Path(file_path + ".bak")
        assert bak_file.exists(), "Backup file should exist"
        assert bak_file.read_text(encoding="utf-8") == original
    finally:
        for p in [Path(file_path), Path(file_path + ".bak")]:
            if p.exists():
                p.unlink()

def test_apply_invalid_javascript_syntax_rollback():
    """Adversarial: Remediated code introduces JavaScript syntax error."""
    with tempfile.NamedTemporaryFile("w+", suffix=".js", delete=False, encoding="utf-8") as f:
        original = 'function getUser(id) {\n    return db.query(`SELECT * FROM users WHERE id = ${id}`);\n}\n'
        f.write(original)
        f.flush()
        file_path = f.name

    try:
        # Corrupted JS syntax: 'const = = ;'
        corrupted_js = 'function getUser(id) {\n    const = = ;\n    return db.query("SELECT * FROM users WHERE id = ?", [id]);\n}\n'
        resp = client.post("/api/apply-patch", json={
            "target_file": file_path,
            "remediated_code": corrupted_js,
            "patch_id": "BAD_PATCH_JS"
        })
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

        # Original file must remain intact!
        current = Path(file_path).read_text(encoding="utf-8")
        assert current == original, "Atomicity violation! JS file corrupted after rejected patch"
    finally:
        for p in [Path(file_path), Path(file_path + ".bak")]:
            if p.exists():
                p.unlink()

def test_apply_invalid_typescript_syntax_rollback():
    """Adversarial: Remediated code introduces TypeScript syntax error."""
    with tempfile.NamedTemporaryFile("w+", suffix=".ts", delete=False, encoding="utf-8") as f:
        original = 'export function findUser(id: string): any {\n    return db.query(`SELECT * FROM users WHERE id = ${id}`);\n}\n'
        f.write(original)
        f.flush()
        file_path = f.name

    try:
        # Corrupted TS syntax
        corrupted_ts = 'export function findUser(id: string ::: ): {\n    return null;\n}\n'
        resp = client.post("/api/apply-patch", json={
            "target_file": file_path,
            "remediated_code": corrupted_ts,
            "patch_id": "BAD_PATCH_TS"
        })
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

        # Original file must remain intact!
        current = Path(file_path).read_text(encoding="utf-8")
        assert current == original, "Atomicity violation! TS file corrupted after rejected patch"
    finally:
        for p in [Path(file_path), Path(file_path + ".bak")]:
            if p.exists():
                p.unlink()

def test_apply_corrupted_unified_diff():
    """Adversarial: Malformed / corrupted unified diff."""
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8") as f:
        original = 'def run():\n    return 42\n'
        f.write(original)
        f.flush()
        file_path = f.name

    try:
        # Malformed diff that introduces syntax errors
        corrupted_diff = '--- a/test.py\n+++ b/test.py\n@@ -1,2 +1,2 @@\n-def run():\n+def run(:\n return 42'
        resp = client.post("/api/apply-patch", json={
            "target_file": file_path,
            "patch_diff": corrupted_diff,
            "patch_id": "CORRUPTED_DIFF_001"
        })
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

        # Original file must remain intact
        current = Path(file_path).read_text(encoding="utf-8")
        assert current == original, "Atomicity violation! File modified by bad diff"
    finally:
        for p in [Path(file_path), Path(file_path + ".bak")]:
            if p.exists():
                p.unlink()

def test_apply_nonexistent_file():
    """Adversarial: Target file does not exist."""
    resp = client.post("/api/apply-patch", json={
        "target_file": "d:/non_existent_folder_abc123/missing.py",
        "remediated_code": "print('hello')",
        "patch_id": "NOT_FOUND"
    })
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"]

def test_apply_empty_payload():
    """Adversarial: Missing both remediated_code and patch_diff."""
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("x = 1\n")
        f.flush()
        file_path = f.name

    try:
        resp = client.post("/api/apply-patch", json={
            "target_file": file_path
        })
        assert resp.status_code == 400
        assert "Either remediated_code or patch_diff" in resp.json()["detail"]
    finally:
        Path(file_path).unlink(missing_ok=True)

if __name__ == "__main__":
    pytest.main(["-v", __file__])

def test_apply_readonly_file_failure():
    """Adversarial: Target file is made read-only."""
    import stat
    custom_client = TestClient(app, raise_server_exceptions=False)
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8") as f:
        original = 'x = 1\n'
        f.write(original)
        f.flush()
        file_path = f.name

    try:
        # Mark read-only
        os.chmod(file_path, stat.S_IREAD)
        resp = custom_client.post("/api/apply-patch", json={
            "target_file": file_path,
            "remediated_code": "x = 2\n",
            "patch_id": "READONLY_TEST"
        })
        # When target file is read-only, write fails; server returns 500
        assert resp.status_code == 500

        # Content must still be original (atomicity preserved)
        current = Path(file_path).read_text(encoding="utf-8")
        assert current == original
    finally:
        import stat
        for p in [Path(file_path), Path(file_path + ".bak")]:
            if p.exists():
                os.chmod(p, stat.S_IWRITE)
                p.unlink()
