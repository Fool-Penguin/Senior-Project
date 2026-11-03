"""
test_adversarial_m1_fix.py - Adversarial Verification Harness for Milestone 1 Iteration 2.

Empirical verification of the patch application pipeline:
1. Fuzzing and corrupt diff payloads (empty hunks, inverted lines, partial context, non-ASCII).
2. Byte-for-byte fidelity on rejected diffs and safety .bak lifecycle.
3. Valid multi-hunk diffs across Python, JavaScript, and TypeScript.
"""

import hashlib
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.main import app
from app.api.scan import get_parser_for_language, detect_language
from app.api.patches import generate_diff

client = TestClient(app)


def sha256_of_file(path: Path) -> str:
    """Compute SHA-256 hash of a file on disk."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ============================================================================
# Dimension 1: Fuzzing and Corrupt Diff Payloads
# ============================================================================

class TestDiffFuzzingAndCorruptPayloads:
    """Stress-test POST /api/apply-patch against fuzzed and malformed diff payloads."""

    def test_empty_diff_and_whitespace(self, tmp_path):
        """Diff with empty string or whitespace only must be rejected."""
        f = tmp_path / "app.py"
        f.write_text("def index():\n    return 'hello'\n", encoding="utf-8")

        # Empty string -> 400 Bad Request (neither remediated_code nor patch_diff supplied)
        resp_empty = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": ""},
        )
        assert resp_empty.status_code == 400
        assert "Either remediated_code or patch_diff" in resp_empty.json()["detail"]

        # Whitespace-only strings -> 422 Unprocessable Content (empty or whitespace-only)
        for bad_diff in ["   ", "\n\n\t  \n"]:
            resp = client.post(
                "/api/apply-patch",
                json={"target_file": str(f), "patch_diff": bad_diff},
            )
            assert resp.status_code == 422
            assert "empty or whitespace-only" in resp.json()["detail"]

    def test_empty_hunk_header_no_content(self, tmp_path):
        """Hunk header with 0 lines and no following lines must be rejected with HTTP 422."""
        f = tmp_path / "app.py"
        f.write_text("x = 1\ny = 2\n", encoding="utf-8")

        empty_hunk = "--- a/app.py\n+++ b/app.py\n@@ -1,0 +1,0 @@\n"
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": empty_hunk},
        )
        assert resp.status_code == 422

    def test_multiple_consecutive_empty_hunks(self, tmp_path):
        """Consecutive empty hunk headers must be rejected with HTTP 422."""
        f = tmp_path / "app.py"
        f.write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")

        diff = "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n@@ -3,1 +3,1 @@\n"
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422

    def test_header_only_diff_no_hunks(self, tmp_path):
        """Diff with unified diff headers but no @@ hunks must be rejected with HTTP 422."""
        f = tmp_path / "app.py"
        f.write_text("x = 1\n", encoding="utf-8")

        diff = "--- a/app.py\n+++ b/app.py\n"
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "No valid @@ hunk headers found" in resp.json()["detail"]

    def test_inverted_line_numbers_out_of_order_hunks(self, tmp_path):
        """Hunk 2 starting before Hunk 1's position must be rejected with HTTP 422."""
        f = tmp_path / "app.py"
        f.write_text(
            "line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7\nline 8\nline 9\nline 10\n",
            encoding="utf-8",
        )

        out_of_order_diff = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -8,2 +8,2 @@\n"
            " line 8\n"
            "-line 9\n"
            "+line 9_mod\n"
            "@@ -3,2 +3,2 @@\n"
            " line 3\n"
            "-line 4\n"
            "+line 4_mod\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": out_of_order_diff},
        )
        assert resp.status_code == 422
        assert "before current line" in resp.json()["detail"]

    def test_negative_and_floating_point_line_numbers(self, tmp_path):
        """Malformed hunk headers with negative or float numbers must be rejected with HTTP 422."""
        f = tmp_path / "app.py"
        f.write_text("x = 1\ny = 2\n", encoding="utf-8")

        for bad_header in [
            "@@ --5,2 +-3,2 @@\n x = 1\n",
            "@@ -1.5,2 +1.5,2 @@\n x = 1\n",
            "@@ -abc,2 +def,2 @@\n x = 1\n",
            "@@ -1,2 @@\n",
            "@@ +1,2 @@\n",
        ]:
            diff = f"--- a/app.py\n+++ b/app.py\n{bad_header}"
            resp = client.post(
                "/api/apply-patch",
                json={"target_file": str(f), "patch_diff": diff},
            )
            assert resp.status_code == 422
            assert ("Malformed hunk header" in resp.json()["detail"] or "No valid @@ hunk headers" in resp.json()["detail"])

    def test_hunk_start_exceeds_file_length(self, tmp_path):
        """Hunk start line beyond EOF must be rejected with HTTP 422."""
        f = tmp_path / "app.py"
        f.write_text("line 1\nline 2\n", encoding="utf-8")

        diff = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -50,2 +50,2 @@\n"
            "-line 50\n"
            "+line 50_new\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "exceeds original file length" in resp.json()["detail"]

    def test_hunk_context_overflows_eof(self, tmp_path):
        """Context lines extending beyond EOF must be rejected with HTTP 422."""
        f = tmp_path / "app.py"
        f.write_text("line 1\nline 2\n", encoding="utf-8")

        diff = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,5 +1,5 @@\n"
            " line 1\n"
            " line 2\n"
            " line 3\n"
            " line 4\n"
            " line 5\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "Context line exceeds original file length" in resp.json()["detail"]

    def test_hunk_deletion_overflows_eof(self, tmp_path):
        """Deletion lines extending beyond EOF must be rejected with HTTP 422."""
        f = tmp_path / "app.py"
        f.write_text("line 1\nline 2\n", encoding="utf-8")

        diff = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,3 +1,1 @@\n"
            " line 1\n"
            "-line 2\n"
            "-line 3\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "Deletion line exceeds original file length" in resp.json()["detail"]

    def test_partial_context_prefix_only_mismatch(self, tmp_path):
        """Context line matching only a prefix of the original line must be rejected."""
        f = tmp_path / "app.py"
        f.write_text("def get_user_by_id(user_id):\n    return user_id\n", encoding="utf-8")

        diff = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def get_user_by_id(\n"
            "-    return user_id\n"
            "+    return None\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "Context mismatch" in resp.json()["detail"]

    def test_partial_context_suffix_only_mismatch(self, tmp_path):
        """Context line matching only a suffix of the original line must be rejected."""
        f = tmp_path / "app.py"
        f.write_text("def get_user_by_id(user_id):\n    return user_id\n", encoding="utf-8")

        diff = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " (user_id):\n"
            "-    return user_id\n"
            "+    return None\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "Context mismatch" in resp.json()["detail"]

    def test_context_case_sensitivity_mismatch(self, tmp_path):
        """Case mismatch in context lines must be rejected."""
        f = tmp_path / "app.py"
        f.write_text("def get_user(req):\n    return req\n", encoding="utf-8")

        diff = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " DEF GET_USER(REQ):\n"
            "-    return req\n"
            "+    return None\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "Context mismatch" in resp.json()["detail"]

    def test_deletion_line_mismatch(self, tmp_path):
        """Mismatch on the line to be deleted must be rejected."""
        f = tmp_path / "app.py"
        f.write_text(
            "def query(uid):\n"
            "    cursor.execute('SELECT * FROM users WHERE id = ' + uid)\n",
            encoding="utf-8",
        )

        diff = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def query(uid):\n"
            "-    cursor.execute('SELECT * FROM accounts WHERE id = ' + uid)\n"
            "+    cursor.execute('SELECT * FROM users WHERE id = %s', (uid,))\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "Deletion mismatch" in resp.json()["detail"]

    def test_unexpected_line_types_in_hunk(self, tmp_path):
        """Lines inside hunk not starting with space, +, -, or backslash must be rejected."""
        f = tmp_path / "app.py"
        f.write_text("def hello():\n    return 1\n", encoding="utf-8")

        for bad_line in ["? unknown operator", "* wildcard line", "! alert line", "def hello():"]:
            diff = (
                "--- a/app.py\n+++ b/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                f"{bad_line}\n"
                "+    return 2\n"
            )
            resp = client.post(
                "/api/apply-patch",
                json={"target_file": str(f), "patch_diff": diff},
            )
            assert resp.status_code == 422
            assert "Unexpected line in hunk" in resp.json()["detail"]

    def test_no_change_diff_rejected(self, tmp_path):
        """Diff producing zero changes to original content must return HTTP 422."""
        f = tmp_path / "app.py"
        orig = "def compute():\n    return 42\n"
        f.write_text(orig, encoding="utf-8")

        # Case 1: Hunk with only context lines
        diff_context_only = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def compute():\n"
            "     return 42\n"
        )
        resp1 = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff_context_only},
        )
        assert resp1.status_code == 422
        assert "produced no changes" in resp1.json()["detail"]

        # Case 2: Hunk deletes and re-adds identical line
        diff_redundant = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def compute():\n"
            "-    return 42\n"
            "+    return 42\n"
        )
        resp2 = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff_redundant},
        )
        assert resp2.status_code == 422
        assert "produced no changes" in resp2.json()["detail"]

    def test_non_ascii_unicode_thai_japanese_emoji(self, tmp_path):
        """Non-ASCII Unicode in target file and diff (Thai, Japanese, Emoji) must succeed."""
        orig_content = (
            "# ระบบจัดการฐานข้อมูลความปลอดภัย 🚀\n"
            "def ค้นหาผู้ใช้(ชื่อผู้ใช้):\n"
            "    # ユーザー名による検索\n"
            "    sql = f'SELECT * FROM บัญชี WHERE ชื่อ = \\'{ชื่อผู้ใช้}\\''\n"
            "    return db.query(sql)\n"
        )
        f = tmp_path / "security_unicode.py"
        f.write_text(orig_content, encoding="utf-8")

        diff = (
            "--- a/security_unicode.py\n+++ b/security_unicode.py\n"
            "@@ -1,5 +1,5 @@\n"
            " # ระบบจัดการฐานข้อมูลความปลอดภัย 🚀\n"
            " def ค้นหาผู้ใช้(ชื่อผู้ใช้):\n"
            "     # ユーザー名による検索\n"
            "-    sql = f'SELECT * FROM บัญชี WHERE ชื่อ = \\'{ชื่อผู้ใช้}\\''\n"
            "-    return db.query(sql)\n"
            "+    sql = 'SELECT * FROM บัญชี WHERE ชื่อ = %s'\n"
            "+    return db.query(sql, (ชื่อผู้ใช้,))\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        updated = f.read_text(encoding="utf-8")
        assert "SELECT * FROM บัญชี WHERE ชื่อ = %s" in updated
        assert "(ชื่อผู้ใช้,)" in updated
        assert "🚀" in updated
        assert "ユーザー名による検索" in updated

    def test_non_ascii_mismatch_rejected(self, tmp_path):
        """Subtle typo in Unicode non-ASCII context line must be rejected with HTTP 422."""
        orig_content = (
            "def ค้นหาผู้ใช้(ชื่อผู้ใช้):\n"
            "    return ชื่อผู้ใช้\n"
        )
        f = tmp_path / "unicode_mismatch.py"
        f.write_text(orig_content, encoding="utf-8")

        # Context has slight Thai typo (ผุ้ vs ผู้)
        diff = (
            "--- a/unicode_mismatch.py\n+++ b/unicode_mismatch.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def ค้นหาผุ้ใช้(ชื่อผู้ใช้):\n"
            "-    return ชื่อผู้ใช้\n"
            "+    return None\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 422
        assert "Context mismatch" in resp.json()["detail"]


# ============================================================================
# Dimension 2: Byte-for-Byte Fidelity and .bak Lifecycle
# ============================================================================

class TestByteForByteIntegrityAndBackupLifecycle:
    """Empirically verify byte-for-byte fidelity and safety .bak handling."""

    def test_byte_for_byte_fidelity_on_all_rejected_diffs(self, tmp_path):
        """Verify target file remains 100% byte-for-byte identical after each rejected diff."""
        orig_bytes = (
            b"# Complex multi-encoding file \xc3\xa9\xc3\xa8\xc3\xa0 \xe0\xb9\x84\xe0\xb8\x97\xe0\xb8\xa2\r\n"
            b"def secure_handler(request):\r\n"
            b"    raw_id = request.args.get('id')\r\n"
            b"    cursor.execute('SELECT * FROM users WHERE id = ' + raw_id)\r\n"
            b"    return cursor.fetchall()\r\n"
        )
        f = tmp_path / "byte_fidelity.py"
        f.write_bytes(orig_bytes)
        initial_hash = hashlib.sha256(orig_bytes).hexdigest()

        corrupt_diffs = [
            # Corrupt A: totally bogus text
            "BOGUS TEXT NO HUNKS",
            # Corrupt B: out-of-order hunks
            "--- a/f\n+++ b/f\n@@ -4,1 +4,1 @@\n cursor\n@@ -2,1 +2,1 @@\n raw_id\n",
            # Corrupt C: context mismatch
            "--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n def nonexistent_func():\n-    x\n+    y\n",
            # Corrupt D: deletion mismatch
            "--- a/f\n+++ b/f\n@@ -1,4 +1,4 @@\n # Complex multi-encoding file\n def secure_handler(request):\n     raw_id = request.args.get('id')\n-    cursor.execute('WRONG DELETION LINE')\n+    pass\n",
            # Corrupt E: no changes
            "--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n def secure_handler(request):\n     raw_id = request.args.get('id')\n",
        ]

        for idx, bad_diff in enumerate(corrupt_diffs):
            resp = client.post(
                "/api/apply-patch",
                json={"target_file": str(f), "patch_diff": bad_diff},
            )
            assert resp.status_code == 422, f"Failed on corrupt diff {idx}"

            # Verify byte-for-byte identity
            current_bytes = f.read_bytes()
            assert current_bytes == orig_bytes, f"Byte corruption detected on case {idx}"
            assert hashlib.sha256(current_bytes).hexdigest() == initial_hash

    def test_backup_created_and_identical_on_rejection(self, tmp_path):
        """Backup .bak file must be created and contain exact original content even when diff fails."""
        orig_content = "def calculate(x, y):\n    return x * y\n"
        f = tmp_path / "backup_on_reject.py"
        f.write_text(orig_content, encoding="utf-8")
        backup = f.with_name(f"{f.name}.bak")

        # Ensure no backup exists initially
        if backup.exists():
            backup.unlink()

        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": "INVALID DIFF"},
        )
        assert resp.status_code == 422

        # Assert .bak was created and is byte-for-byte identical to orig_content
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == orig_content
        # Assert target file was not modified
        assert f.read_text(encoding="utf-8") == orig_content

    def test_consecutive_patches_lifecycle(self, tmp_path):
        """
        Verify multi-iteration patching lifecycle:
        v1 (orig) -> v2 (successful patch 1) -> corrupt patch rejected (stays v2) -> v3 (successful patch 2).
        """
        v1 = "def query(uid):\n    return 'SELECT * FROM t WHERE id = ' + uid\n"
        f = tmp_path / "lifecycle.py"
        f.write_text(v1, encoding="utf-8")
        backup = f.with_name(f"{f.name}.bak")

        # 1. Patch 1 (v1 -> v2)
        diff_v1_to_v2 = (
            "--- a/lifecycle.py\n+++ b/lifecycle.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def query(uid):\n"
            "-    return 'SELECT * FROM t WHERE id = ' + uid\n"
            "+    return 'SELECT * FROM t WHERE id = %s', (uid,)\n"
        )
        resp1 = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff_v1_to_v2},
        )
        assert resp1.status_code == 200
        v2 = f.read_text(encoding="utf-8")
        assert "SELECT * FROM t WHERE id = %s" in v2
        assert backup.read_text(encoding="utf-8") == v1

        # 2. Corrupt Patch attempted on v2 -> rejected
        resp_corrupt = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": "MALFORMED DIFF"},
        )
        assert resp_corrupt.status_code == 422
        # Target file must still be v2 byte-for-byte
        assert f.read_text(encoding="utf-8") == v2
        # Backup file now contains v2 (captured before the failed attempt)
        assert backup.read_text(encoding="utf-8") == v2

        # 3. Patch 2 (v2 -> v3)
        diff_v2_to_v3 = (
            "--- a/lifecycle.py\n+++ b/lifecycle.py\n"
            "@@ -1,2 +1,3 @@\n"
            " def query(uid):\n"
            "+    # Verified sanitized query\n"
            "     return 'SELECT * FROM t WHERE id = %s', (uid,)\n"
        )
        resp2 = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff_v2_to_v3},
        )
        assert resp2.status_code == 200
        v3 = f.read_text(encoding="utf-8")
        assert "# Verified sanitized query" in v3
        assert backup.read_text(encoding="utf-8") == v2

    def test_syntax_error_rollback_and_backup(self, tmp_path):
        """Diff producing Tree-sitter CST syntax error is rejected with 422 and rolled back."""
        orig_content = "def greet(name):\n    return f'Hello, {name}'\n"
        f = tmp_path / "syntax_rollback.py"
        f.write_text(orig_content, encoding="utf-8")
        backup = f.with_name(f"{f.name}.bak")

        syntax_broken_diff = (
            "--- a/syntax_rollback.py\n+++ b/syntax_rollback.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def greet(name):\n"
            "-    return f'Hello, {name}'\n"
            "+    return (((( SYNTAX ERROR ??? @@@\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": syntax_broken_diff},
        )
        assert resp.status_code == 422
        assert "invalid CST syntax" in resp.json()["detail"]

        # Target file must remain original
        assert f.read_text(encoding="utf-8") == orig_content
        assert backup.read_text(encoding="utf-8") == orig_content


# ============================================================================
# Dimension 3: Valid Multi-Hunk Diffs Across Python, JavaScript, and TypeScript
# ============================================================================

class TestValidMultiHunkDiffsAcrossLanguages:
    """Verify clean application of valid multi-hunk diffs across Python, JS, and TS."""

    def test_valid_python_multi_hunk_diff(self, tmp_path):
        """Python file with 3 separate separated hunks applied accurately with 0 CST errors."""
        orig_py = (
            "import os\n"
            "import sys\n"
            "\n"
            "# --- Utility Block ---\n"
            "def util_a():\n"
            "    return 1\n"
            "\n"
            "def util_b():\n"
            "    return 2\n"
            "\n"
            "def util_c():\n"
            "    return 3\n"
            "\n"
            "def login_user(req):\n"
            "    user = req.args.get('user')\n"
            "    pwd = req.args.get('pwd')\n"
            "    query = f\"SELECT * FROM users WHERE user='{user}' AND pwd='{pwd}'\"\n"
            "    return db.execute(query)\n"
            "\n"
            "# --- Middle Handler Block ---\n"
            "def mid_a():\n"
            "    return 'a'\n"
            "\n"
            "def mid_b():\n"
            "    return 'b'\n"
            "\n"
            "def mid_c():\n"
            "    return 'c'\n"
            "\n"
            "def search_products(req):\n"
            "    keyword = req.args.get('q')\n"
            "    sql = \"SELECT * FROM items WHERE name LIKE '%\" + keyword + \"%'\"\n"
            "    return db.execute(sql)\n"
            "\n"
            "def status_check():\n"
            "    return {'status': 'healthy'}\n"
        )
        patched_py = (
            "import os\n"
            "import sqlite3\n"
            "import sys\n"
            "\n"
            "# --- Utility Block ---\n"
            "def util_a():\n"
            "    return 1\n"
            "\n"
            "def util_b():\n"
            "    return 2\n"
            "\n"
            "def util_c():\n"
            "    return 3\n"
            "\n"
            "def login_user(req):\n"
            "    user = req.args.get('user')\n"
            "    pwd = req.args.get('pwd')\n"
            "    query = \"SELECT * FROM users WHERE user = %s AND pwd = %s\"\n"
            "    return db.execute(query, (user, pwd))\n"
            "\n"
            "# --- Middle Handler Block ---\n"
            "def mid_a():\n"
            "    return 'a'\n"
            "\n"
            "def mid_b():\n"
            "    return 'b'\n"
            "\n"
            "def mid_c():\n"
            "    return 'c'\n"
            "\n"
            "def search_products(req):\n"
            "    keyword = req.args.get('q')\n"
            "    sql = \"SELECT * FROM items WHERE name LIKE %s\"\n"
            "    return db.execute(sql, (f\"%{keyword}%\",))\n"
            "\n"
            "def status_check():\n"
            "    return {'status': 'healthy'}\n"
        )
        f = tmp_path / "multi_hunk_app.py"
        f.write_text(orig_py, encoding="utf-8")

        # Generate canonical 3-hunk unified diff via the server's generate_diff
        multi_diff = generate_diff(orig_py, patched_py, "multi_hunk_app.py")
        hunk_headers = [line for line in multi_diff.splitlines() if line.startswith("@@")]
        assert len(hunk_headers) == 3, f"Expected 3 hunks, got {len(hunk_headers)}:\n{multi_diff}"

        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": multi_diff},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        applied = f.read_text(encoding="utf-8")
        assert "import sqlite3" in applied
        assert "user = %s AND pwd = %s" in applied
        assert "db.execute(query, (user, pwd))" in applied
        assert "items WHERE name LIKE %s" in applied
        assert "db.execute(sql, (f\"%{keyword}%\",))" in applied
        assert applied.strip() == patched_py.strip()

        # Tree-sitter CST syntax verification
        parser = get_parser_for_language("python")
        tree = parser.parse(applied.encode("utf-8"))
        assert not tree.root_node.has_error

    def test_valid_javascript_multi_hunk_diff(self, tmp_path):
        """JavaScript file with 3 separate separated hunks applied accurately with 0 CST errors."""
        orig_js = (
            "const express = require('express');\n"
            "const app = express();\n"
            "\n"
            "// Middle padding handlers\n"
            "function logRequest(req) { console.log(req.url); }\n"
            "function validateHeader(req) { return true; }\n"
            "function metricsMiddleware(req) { return Date.now(); }\n"
            "\n"
            "app.get('/users', async (req, res) => {\n"
            "    const id = req.query.id;\n"
            "    const sql = `SELECT * FROM users WHERE id = ${id}`;\n"
            "    const rows = await db.query(sql);\n"
            "    res.json(rows);\n"
            "});\n"
            "\n"
            "// Second padding block\n"
            "function cacheLookup(key) { return null; }\n"
            "function cacheSet(key, val) { return true; }\n"
            "function authCheck(token) { return token != null; }\n"
            "\n"
            "app.get('/search', async (req, res) => {\n"
            "    const q = req.query.q;\n"
            "    const raw = 'SELECT * FROM docs WHERE title = \\'' + q + '\\'';\n"
            "    const docs = await db.query(raw);\n"
            "    res.json(docs);\n"
            "});\n"
            "\n"
            "module.exports = app;\n"
        )
        patched_js = (
            "const express = require('express');\n"
            "const db = require('./db');\n"
            "const app = express();\n"
            "\n"
            "// Middle padding handlers\n"
            "function logRequest(req) { console.log(req.url); }\n"
            "function validateHeader(req) { return true; }\n"
            "function metricsMiddleware(req) { return Date.now(); }\n"
            "\n"
            "app.get('/users', async (req, res) => {\n"
            "    const id = req.query.id;\n"
            "    const sql = 'SELECT * FROM users WHERE id = $1';\n"
            "    const rows = await db.query(sql, [id]);\n"
            "    res.json(rows);\n"
            "});\n"
            "\n"
            "// Second padding block\n"
            "function cacheLookup(key) { return null; }\n"
            "function cacheSet(key, val) { return true; }\n"
            "function authCheck(token) { return token != null; }\n"
            "\n"
            "app.get('/search', async (req, res) => {\n"
            "    const q = req.query.q;\n"
            "    const raw = 'SELECT * FROM docs WHERE title = $1';\n"
            "    const docs = await db.query(raw, [q]);\n"
            "    res.json(docs);\n"
            "});\n"
            "\n"
            "module.exports = app;\n"
        )
        f = tmp_path / "server_routes.js"
        f.write_text(orig_js, encoding="utf-8")

        # Canonical multi-hunk unified diff
        multi_js_diff = generate_diff(orig_js, patched_js, "server_routes.js")
        hunk_headers = [line for line in multi_js_diff.splitlines() if line.startswith("@@")]
        assert len(hunk_headers) == 3, f"Expected 3 hunks, got {len(hunk_headers)}:\n{multi_js_diff}"

        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": multi_js_diff},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        applied = f.read_text(encoding="utf-8")
        assert "const db = require('./db');" in applied
        assert "WHERE id = $1" in applied
        assert "db.query(sql, [id])" in applied
        assert "WHERE title = $1" in applied
        assert "db.query(raw, [q])" in applied
        assert applied.strip() == patched_js.strip()

        # Tree-sitter CST syntax verification
        parser = get_parser_for_language("javascript")
        tree = parser.parse(applied.encode("utf-8"))
        assert not tree.root_node.has_error

    def test_valid_typescript_multi_hunk_diff(self, tmp_path):
        """TypeScript file with 3 separate separated hunks applied accurately with 0 CST errors."""
        orig_ts = (
            "import { Request, Response } from 'express';\n"
            "import { Pool } from 'pg';\n"
            "\n"
            "export interface UserRecord {\n"
            "    id: string;\n"
            "    name: string;\n"
            "}\n"
            "\n"
            "// Helper padding functions\n"
            "export function formatUser(u: UserRecord): string { return u.name; }\n"
            "export function parseUserId(raw: string): number { return parseInt(raw, 10); }\n"
            "export function isEmail(s: string): boolean { return s.includes('@'); }\n"
            "\n"
            "export class UserService {\n"
            "    constructor(private pool: Pool) {}\n"
            "\n"
            "    async findById(req: Request): Promise<UserRecord[]> {\n"
            "        const userId = req.params.userId;\n"
            "        const query = `SELECT * FROM accounts WHERE id = '${userId}'`;\n"
            "        const result = await this.pool.query<UserRecord>(query);\n"
            "        return result.rows;\n"
            "    }\n"
            "\n"
            "    // Additional service methods padding\n"
            "    async countActive(): Promise<number> { return 42; }\n"
            "    async purgeInactive(): Promise<void> {}\n"
            "    async getHealth(): Promise<boolean> { return true; }\n"
            "\n"
            "    async findByEmail(email: string): Promise<UserRecord | null> {\n"
            "        const q = \"SELECT * FROM accounts WHERE email = '\" + email + \"'\";\n"
            "        const res = await this.pool.query<UserRecord>(q);\n"
            "        return res.rows[0] || null;\n"
            "    }\n"
            "}\n"
        )
        patched_ts = (
            "import { Request, Response } from 'express';\n"
            "import { Pool } from 'pg';\n"
            "\n"
            "export interface UserRecord {\n"
            "    id: string;\n"
            "    name: string;\n"
            "    email: string;\n"
            "}\n"
            "\n"
            "// Helper padding functions\n"
            "export function formatUser(u: UserRecord): string { return u.name; }\n"
            "export function parseUserId(raw: string): number { return parseInt(raw, 10); }\n"
            "export function isEmail(s: string): boolean { return s.includes('@'); }\n"
            "\n"
            "export class UserService {\n"
            "    constructor(private pool: Pool) {}\n"
            "\n"
            "    async findById(req: Request): Promise<UserRecord[]> {\n"
            "        const userId = req.params.userId;\n"
            "        const query = 'SELECT * FROM accounts WHERE id = $1';\n"
            "        const result = await this.pool.query<UserRecord>(query, [userId]);\n"
            "        return result.rows;\n"
            "    }\n"
            "\n"
            "    // Additional service methods padding\n"
            "    async countActive(): Promise<number> { return 42; }\n"
            "    async purgeInactive(): Promise<void> {}\n"
            "    async getHealth(): Promise<boolean> { return true; }\n"
            "\n"
            "    async findByEmail(email: string): Promise<UserRecord | null> {\n"
            "        const q = 'SELECT * FROM accounts WHERE email = $1';\n"
            "        const res = await this.pool.query<UserRecord>(q, [email]);\n"
            "        return res.rows[0] || null;\n"
            "    }\n"
            "}\n"
        )
        f = tmp_path / "user_service.ts"
        f.write_text(orig_ts, encoding="utf-8")

        # Canonical multi-hunk unified diff
        multi_ts_diff = generate_diff(orig_ts, patched_ts, "user_service.ts")
        hunk_headers = [line for line in multi_ts_diff.splitlines() if line.startswith("@@")]
        assert len(hunk_headers) == 3, f"Expected 3 hunks, got {len(hunk_headers)}:\n{multi_ts_diff}"

        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": multi_ts_diff},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        applied = f.read_text(encoding="utf-8")
        assert "email: string;" in applied
        assert "WHERE id = $1" in applied
        assert "this.pool.query<UserRecord>(query, [userId])" in applied
        assert "WHERE email = $1" in applied
        assert "this.pool.query<UserRecord>(q, [email])" in applied
        assert applied.strip() == patched_ts.strip()

        # Tree-sitter CST syntax verification for TypeScript
        parser = get_parser_for_language("typescript")
        tree = parser.parse(applied.encode("utf-8"))
        assert not tree.root_node.has_error

    def test_zero_line_insertion_at_top_of_file(self, tmp_path):
        """Zero-line insertion hunk (@@ -0,0 +1,2 @@) at top of file."""
        orig = "def hello():\n    return 1\n"
        f = tmp_path / "zero_insert_top.py"
        f.write_text(orig, encoding="utf-8")

        diff = (
            "--- a/zero_insert_top.py\n+++ b/zero_insert_top.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+# Top header line 1\n"
            "+# Top header line 2\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 200

        applied = f.read_text(encoding="utf-8")
        assert applied.startswith("# Top header line 1\n# Top header line 2\ndef hello():\n")

    def test_single_line_hunk_header_format(self, tmp_path):
        """Hunk headers using single line syntax without commas (@@ -2 +2 @@)."""
        orig = "x = 1\ny = 2\nz = 3\n"
        f = tmp_path / "single_line.py"
        f.write_text(orig, encoding="utf-8")

        diff = (
            "--- a/single_line.py\n+++ b/single_line.py\n"
            "@@ -2 +2 @@\n"
            "-y = 2\n"
            "+y = 200\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 200

        applied = f.read_text(encoding="utf-8")
        assert applied == "x = 1\ny = 200\nz = 3\n"

    def test_windows_crlf_newline_preservation(self, tmp_path):
        """Target files with CRLF (\\r\\n) line endings retain CRLF after patching."""
        orig_crlf = "def foo():\r\n    x = 1\r\n    return x\r\n"
        f = tmp_path / "crlf_file.py"
        f.write_bytes(orig_crlf.encode("utf-8"))

        diff = (
            "--- a/crlf_file.py\n+++ b/crlf_file.py\n"
            "@@ -1,3 +1,3 @@\n"
            " def foo():\n"
            "-    x = 1\n"
            "+    x = 99\n"
            "     return x\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        assert resp.status_code == 200

        raw_bytes = f.read_bytes()
        assert b"\r\n" in raw_bytes
        assert b"x = 99\r\n" in raw_bytes
        assert b"\n" not in raw_bytes.replace(b"\r\n", b"")

    def test_massive_multi_hunk_stress(self, tmp_path):
        """Massive 5-hunk diff separated by large blocks applied accurately across a large file."""
        lines = [
            f"def func_{i}():\n    # padding line 1\n    # padding line 2\n    # padding line 3\n    # padding line 4\n    val = {i}\n    return val\n"
            for i in range(15)
        ]
        orig_code = "".join(lines)
        
        # Patch every 3rd function (0, 3, 6, 9, 12) -> exactly 5 distinct hunks separated by >14 lines
        patched_lines = list(lines)
        for i in range(0, 15, 3):
            patched_lines[i] = (
                f"def func_{i}():\n    # padding line 1\n    # padding line 2\n    # padding line 3\n    # padding line 4\n    val = {i + 100}\n    return val\n"
            )
        patched_code = "".join(patched_lines)

        f = tmp_path / "massive_app.py"
        f.write_text(orig_code, encoding="utf-8")

        massive_diff = generate_diff(orig_code, patched_code, "massive_app.py")
        hunk_headers = [l for l in massive_diff.splitlines() if l.startswith("@@")]
        assert len(hunk_headers) == 5, f"Expected 5 hunks, got {len(hunk_headers)}"

        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": massive_diff},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        result_code = f.read_text(encoding="utf-8")
        assert result_code.strip() == patched_code.strip()

        # Syntax check
        parser = get_parser_for_language("python")
        tree = parser.parse(result_code.encode("utf-8"))
        assert not tree.root_node.has_error

    def test_binary_null_byte_payload_rejection(self, tmp_path):
        """Diff payload containing binary null bytes is handled safely without crashing."""
        f = tmp_path / "null_byte.py"
        f.write_text("x = 1\n", encoding="utf-8")

        null_diff = "--- a/null_byte.py\n+++ b/null_byte.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = \x00\n"
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": null_diff},
        )
        # Should be rejected with 422 (Tree-sitter syntax error or diff parsing error)
        assert resp.status_code == 422
        # Target file remains unmodified
        assert f.read_text(encoding="utf-8") == "x = 1\n"

    def test_empty_target_file_creation(self, tmp_path):
        """Patching an empty 0-byte file with an insertion hunk."""
        f = tmp_path / "empty_target.py"
        f.write_text("", encoding="utf-8")

        insert_diff = (
            "--- a/empty_target.py\n+++ b/empty_target.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+def initial_handler():\n"
            "+    return 'created'\n"
            "+\n"
        )
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": insert_diff},
        )
        assert resp.status_code == 200

        content = f.read_text(encoding="utf-8")
        assert "def initial_handler():" in content

    def test_nonexistent_target_file_rejection(self, tmp_path):
        """Target file that does not exist returns HTTP 404."""
        nonexistent = tmp_path / "does_not_exist_anywhere.py"
        resp = client.post(
            "/api/apply-patch",
            json={"target_file": str(nonexistent), "patch_diff": "diff text"},
        )
        assert resp.status_code == 404
        assert "Target file does not exist" in resp.json()["detail"]

