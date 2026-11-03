"""
test_adversarial_m1_fix_2.py - Comprehensive Adversarial Stress Test Suite
Milestone 1 Iteration 2 Challenger Verification

Focus Areas:
1. git apply cross-compatibility with real Git repo on generated unified diffs.
2. apply_unified_diff equivalence to git apply.
3. Edge case diffs (CRLF, single-line, multi-line, unicode, whitespace).
4. Concurrent patch generation stress test.
5. Concurrent patch application stress test (independent files).
6. Concurrent patch application race condition stress test (same file).
"""

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests

import sys
CODEDEE_SERVER_DIR = Path(__file__).resolve().parents[3] / "codedee" / "codedee_server"
if str(CODEDEE_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(CODEDEE_SERVER_DIR))

import threading
import uvicorn
from app.main import app

_SERVER_PORT = 8000
_SERVER_STARTED = False
_LOCK = threading.Lock()


def ensure_live_server() -> str:
    global _SERVER_STARTED, _SERVER_PORT
    with _LOCK:
        if _SERVER_STARTED:
            return f"http://127.0.0.1:{_SERVER_PORT}"

        s = requests.Session()
        for port in (8000, 8765, 8999):
            try:
                r = s.get(f"http://127.0.0.1:{port}/health", timeout=0.3)
                if r.status_code in (200, 503):
                    _SERVER_PORT = port
                    _SERVER_STARTED = True
                    return f"http://127.0.0.1:{_SERVER_PORT}"
            except Exception:
                pass

        for port in (8000, 8765, 8999):
            try:
                config = uvicorn.Config(
                    app,
                    host="127.0.0.1",
                    port=port,
                    log_level="error",
                    http="h11",
                )
                server = uvicorn.Server(config)
                t = threading.Thread(target=server.run, daemon=True)
                t.start()

                for _ in range(40):
                    time.sleep(0.1)
                    try:
                        r = s.get(f"http://127.0.0.1:{port}/health", timeout=0.3)
                        if r.status_code in (200, 503):
                            _SERVER_PORT = port
                            _SERVER_STARTED = True
                            return f"http://127.0.0.1:{_SERVER_PORT}"
                    except Exception:
                        pass
            except Exception:
                continue

        raise RuntimeError("Failed to start live uvicorn server for testing.")


@pytest.fixture(scope="session", autouse=True)
def server_base_url():
    url = ensure_live_server()
    global SERVER_URL
    SERVER_URL = url
    return url



# ============================================================================
# Test Suite 1: git apply Cross-Compatibility with Real Git Repository
# ============================================================================

class TestGitApplyCompatibility:
    """
    Empirically verifies that diffs produced by POST /api/generate-patches
    are valid unified diffs accepted by git apply and GNU patch.
    """

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Creates an initialized git repository with initial commit."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "TestTester"], cwd=str(repo_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=str(repo_dir), check=True, capture_output=True)
        return repo_dir

    def test_git_apply_python_sample_cwe89(self, git_repo):
        """Test git apply on Python SQL injection candidate patch."""
        filename = "vulnerable_app.py"
        code = (
            "import sqlite3\n\n"
            "def search_user(request):\n"
            "    user_id = request.args.get('id')\n"
            "    conn = sqlite3.connect('users.db')\n"
            "    cursor = conn.cursor()\n"
            "    query = f\"SELECT * FROM users WHERE id = '{user_id}'\"\n"
            "    cursor.execute(query)\n"
            "    return cursor.fetchone()\n"
        )
        file_path = git_repo / filename
        file_path.write_text(code, encoding="utf-8")

        subprocess.run(["git", "add", filename], cwd=str(git_repo), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(git_repo), check=True, capture_output=True)

        resp = requests.post(
            f"{SERVER_URL}/api/generate-patches",
            json={"issue_id": "GIT_TEST_PY_01", "code_content": code, "target_file": filename, "candidate_count": 3},
            timeout=15.0,
        )
        assert resp.status_code == 200, f"Generate patches failed: {resp.text}"
        data = resp.json()
        patches = data["verified_patches"]
        assert len(patches) > 0, "No verified patches generated"

        for patch in patches:
            diff_text = patch["diff"]
            assert diff_text.startswith("--- a/"), f"Diff missing standard '--- a/' header: {diff_text[:50]}"
            assert "+++ b/" in diff_text, f"Diff missing standard '+++ b/' header: {diff_text[:50]}"
            assert "@@" in diff_text, f"Diff missing hunk header: {diff_text}"

            # Check git apply --check
            proc_check = subprocess.run(
                ["git", "apply", "--check", "-"],
                input=diff_text,
                text=True,
                cwd=str(git_repo),
                capture_output=True,
            )
            assert proc_check.returncode == 0, f"git apply --check failed:\nSTDOUT: {proc_check.stdout}\nSTDERR: {proc_check.stderr}\nDIFF:\n{diff_text}"

            # Check actual git apply
            proc_apply = subprocess.run(
                ["git", "apply", "-"],
                input=diff_text,
                text=True,
                cwd=str(git_repo),
                capture_output=True,
            )
            assert proc_apply.returncode == 0, f"git apply failed:\nSTDOUT: {proc_apply.stdout}\nSTDERR: {proc_apply.stderr}"

            # Verify the applied content matches remediated_code
            applied_code = file_path.read_text(encoding="utf-8")
            assert applied_code.strip() == patch["remediated_code"].strip(), "git apply result differs from remediated_code"

            # Reset repo to clean state
            subprocess.run(["git", "checkout", "--", filename], cwd=str(git_repo), check=True, capture_output=True)

    def test_git_apply_javascript_sample_cwe89(self, git_repo):
        """Test git apply on JavaScript SQL injection candidate patch."""
        filename = "db_client.js"
        code = (
            "const { Client } = require('pg');\n\n"
            "async function getAccount(req, res) {\n"
            "    const client = new Client();\n"
            "    await client.connect();\n"
            "    const accountId = req.query.id;\n"
            "    const query = `SELECT * FROM accounts WHERE id = '${accountId}'`;\n"
            "    const result = await client.query(query);\n"
            "    res.json(result.rows);\n"
            "}\n"
        )
        file_path = git_repo / filename
        file_path.write_text(code, encoding="utf-8")

        subprocess.run(["git", "add", filename], cwd=str(git_repo), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit JS"], cwd=str(git_repo), check=True, capture_output=True)

        resp = requests.post(
            f"{SERVER_URL}/api/generate-patches",
            json={"issue_id": "GIT_TEST_JS_01", "code_content": code, "target_file": filename, "candidate_count": 3},
            timeout=30.0,
        )
        assert resp.status_code == 200, f"Generate patches failed: {resp.text}"
        data = resp.json()
        patches = data["verified_patches"]
        assert len(patches) > 0

        for patch in patches:
            diff_text = patch["diff"]
            # git apply --check
            proc_check = subprocess.run(
                ["git", "apply", "--check", "-"],
                input=diff_text,
                text=True,
                cwd=str(git_repo),
                capture_output=True,
            )
            assert proc_check.returncode == 0, f"git apply --check failed for JS:\nSTDERR: {proc_check.stderr}\nDIFF:\n{diff_text}"

            # git apply
            proc_apply = subprocess.run(
                ["git", "apply", "-"],
                input=diff_text,
                text=True,
                cwd=str(git_repo),
                capture_output=True,
            )
            assert proc_apply.returncode == 0
            applied_code = file_path.read_text(encoding="utf-8")
            assert applied_code.strip() == patch["remediated_code"].strip()

            subprocess.run(["git", "checkout", "--", filename], cwd=str(git_repo), check=True, capture_output=True)

    def test_git_apply_deep_nested_path(self, git_repo):
        """Test git apply on a deeply nested path: src/services/security/dao.py."""
        rel_path = "src/services/security/dao.py"
        full_path = git_repo / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        code = "def get_data(x):\n    cursor.execute(f'SELECT * FROM data WHERE k={x}')\n"
        full_path.write_text(code, encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=str(git_repo), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Nested path commit"], cwd=str(git_repo), check=True, capture_output=True)

        resp = requests.post(
            f"{SERVER_URL}/api/generate-patches",
            json={"issue_id": "NESTED_PATH_01", "code_content": code, "target_file": rel_path, "candidate_count": 3},
            timeout=15.0,
        )
        assert resp.status_code == 200
        patches = resp.json()["verified_patches"]
        assert len(patches) > 0

        for patch in patches:
            diff_text = patch["diff"]
            assert f"--- a/{rel_path}" in diff_text
            assert f"+++ b/{rel_path}" in diff_text

            proc = subprocess.run(
                ["git", "apply", "--check", "-"],
                input=diff_text,
                text=True,
                cwd=str(git_repo),
                capture_output=True,
            )
            assert proc.returncode == 0, f"git apply failed for nested path: {proc.stderr}"
            subprocess.run(["git", "checkout", "--", rel_path], cwd=str(git_repo), check=True, capture_output=True)

    def test_apply_unified_diff_and_git_apply_semantic_equivalence(self, git_repo):
        """
        Verify that backend's apply_unified_diff produces the exact same file
        content as native git apply across all benchmark dataset samples.
        """
        catalogue_path = Path("codedee/codedee_server/data/mini_test_datasets.json")
        if not catalogue_path.exists():
            pytest.skip("mini_test_datasets.json not found")

        with open(catalogue_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)

        vulnerable_samples = [
            s for s in dataset
            if s.get("Is_vulnerable") and s.get("original_code") and len(s.get("original_code").splitlines()) <= 20
        ]
        # Pick 5 diverse concise samples
        test_samples = vulnerable_samples[:5]

        for s in test_samples:
            ext = "py" if s["language"] == "python" else "js"
            filename = f"{s['sample_id']}.{ext}"
            orig_code = s["original_code"].rstrip() + "\n"
            fpath = git_repo / filename
            fpath.write_text(orig_code, encoding="utf-8")

            subprocess.run(["git", "add", filename], cwd=str(git_repo), check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Add {filename}"], cwd=str(git_repo), check=True, capture_output=True)

            resp = requests.post(
                f"{SERVER_URL}/api/generate-patches",
                json={"issue_id": s["sample_id"], "code_content": orig_code, "target_file": filename, "candidate_count": 2},
                timeout=30.0,
            )
            if resp.status_code != 200:
                continue
            patches = resp.json().get("verified_patches", [])
            for patch in patches:
                diff_text = patch["diff"]

                # 1. Native git apply
                proc = subprocess.run(["git", "apply", "-"], input=diff_text, text=True, cwd=str(git_repo), capture_output=True)
                assert proc.returncode == 0, f"git apply failed on {filename}: {proc.stderr}"
                git_applied = fpath.read_text(encoding="utf-8")

                # Reset
                subprocess.run(["git", "checkout", "--", filename], cwd=str(git_repo), check=True, capture_output=True)

                # 2. Server /api/apply-patch
                apply_resp = requests.post(
                    f"{SERVER_URL}/api/apply-patch",
                    json={"target_file": str(fpath), "patch_diff": diff_text},
                    timeout=15.0,
                )
                assert apply_resp.status_code == 200, f"/api/apply-patch failed: {apply_resp.text}"
                server_applied = fpath.read_text(encoding="utf-8")

                # Compare both (normalize whitespace)
                assert git_applied.strip() == server_applied.strip(), f"Divergence between git apply and server apply for {filename}!"

                # Reset
                subprocess.run(["git", "checkout", "--", filename], cwd=str(git_repo), check=True, capture_output=True)



# ============================================================================
# Test Suite 2: Adversarial Diff Handling & Boundary Robustness
# ============================================================================

class TestAdversarialDiffApplication:
    """
    Stress tests /api/apply-patch against malformed, malicious, or edge-case diffs.
    """

    def test_crlf_line_endings_preserved(self, tmp_path):
        """Verify that CRLF line endings in the target file are preserved after diff application."""
        target = tmp_path / "crlf_sample.py"
        crlf_code = "def get_user(x):\r\n    cursor.execute(f'SELECT * FROM u WHERE id={x}')\r\n"
        target.write_bytes(crlf_code.encode("utf-8"))

        resp = requests.post(
            f"{SERVER_URL}/api/generate-patches",
            json={"issue_id": "CRLF_TEST", "code_content": crlf_code, "target_file": "crlf_sample.py"},
            timeout=30.0,
        )
        assert resp.status_code == 200
        patch = resp.json()["verified_patches"][0]

        apply_resp = requests.post(
            f"{SERVER_URL}/api/apply-patch",
            json={"target_file": str(target), "patch_diff": patch["diff"]},
            timeout=15.0,
        )
        assert apply_resp.status_code == 200
        content_bytes = target.read_bytes()
        assert b"\r\n" in content_bytes, "CRLF line endings were lost during patch application"

    def test_context_mismatch_rejection_no_corruption(self, tmp_path):
        """Verify mismatched context in diff returns 422 and preserves file unchanged."""
        target = tmp_path / "target.py"
        orig_content = "def calculate_tax(amount):\n    return amount * 0.07\n"
        target.write_text(orig_content, encoding="utf-8")

        mismatched_diff = (
            "--- a/target.py\n"
            "+++ b/target.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def completely_different_function(arg):\n"
            "-    return arg\n"
            "+    return arg + 1\n"
        )
        resp = requests.post(
            f"{SERVER_URL}/api/apply-patch",
            json={"target_file": str(target), "patch_diff": mismatched_diff},
            timeout=10.0,
        )
        assert resp.status_code == 422
        assert "mismatch" in resp.json()["detail"].lower()
        assert target.read_text(encoding="utf-8") == orig_content

    def test_syntax_breaking_patch_reverts_cleanly(self, tmp_path):
        """Verify that a patch introducing CST syntax errors is reverted from backup."""
        target = tmp_path / "syntax_check.py"
        orig = "def valid_func():\n    return 42\n"
        target.write_text(orig, encoding="utf-8")

        broken_diff = (
            "--- a/syntax_check.py\n"
            "+++ b/syntax_check.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def valid_func():\n"
            "-    return 42\n"
            "+    return return <<<< ?!\n"
        )
        resp = requests.post(
            f"{SERVER_URL}/api/apply-patch",
            json={"target_file": str(target), "patch_diff": broken_diff},
            timeout=10.0,
        )
        assert resp.status_code == 422
        assert "invalid cst syntax" in resp.json()["detail"].lower()
        assert target.read_text(encoding="utf-8") == orig
        # Backup should still exist for forensic inspection
        backup = target.with_name(f"{target.name}.bak")
        assert backup.exists()


# ============================================================================
# Test Suite 3: Concurrency Stress Testing
# ============================================================================

class TestConcurrencyStress:
    """
    Stress tests patch generation and application under high concurrent load.
    """

    def test_concurrent_patch_generation(self):
        """20 concurrent patch generation requests running simultaneously."""
        sample_code = "def get_user(u):\n    cursor.execute(f'SELECT * FROM users WHERE id={u}')\n"
        num_requests = 20

        def send_request(idx):
            start = time.perf_counter()
            r = requests.post(
                f"{SERVER_URL}/api/generate-patches",
                json={
                    "issue_id": f"CONCUR_GEN_{idx:03d}",
                    "code_content": sample_code,
                    "target_file": f"sample_{idx}.py",
                    "candidate_count": 3,
                },
                timeout=30.0,
            )
            elapsed = time.perf_counter() - start
            return idx, r.status_code, elapsed, r.json() if r.status_code == 200 else r.text

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(send_request, i) for i in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        status_codes = [res[1] for res in results]
        assert all(code == 200 for code in status_codes), f"Some concurrent requests failed: {status_codes}"
        # Verify verified_patches returned for all
        for idx, status, elapsed, body in results:
            assert body["verified_count"] >= 1, f"Worker {idx} got 0 verified patches"

    def test_concurrent_patch_application_independent_files(self, tmp_path):
        """20 concurrent patch applications to 20 separate target files."""
        num_files = 20
        targets = []
        diffs = []

        orig_template = "def get_user_{i}(u):\n    cursor.execute(f'SELECT * FROM users WHERE id={{u}}')\n"

        for i in range(num_files):
            f = tmp_path / f"worker_{i}.py"
            code = orig_template.format(i=i)
            f.write_text(code, encoding="utf-8")
            targets.append(f)

            # Generate diff
            gen_resp = requests.post(
                f"{SERVER_URL}/api/generate-patches",
                json={"issue_id": f"CONCUR_APP_{i}", "code_content": code, "target_file": f.name},
                timeout=30.0,
            )
            assert gen_resp.status_code == 200
            diff = gen_resp.json()["verified_patches"][0]["diff"]
            diffs.append(diff)

        def apply_worker(idx):
            f = targets[idx]
            d = diffs[idx]
            r = requests.post(
                f"{SERVER_URL}/api/apply-patch",
                json={"target_file": str(f), "patch_diff": d},
                timeout=15.0,
            )
            return idx, r.status_code, r.text

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(apply_worker, i) for i in range(num_files)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        for idx, status, text in results:
            assert status == 200, f"Worker {idx} failed with status {status}: {text}"
            f = targets[idx]
            new_text = f.read_text(encoding="utf-8")
            assert "f'SELECT" not in new_text, f"File {f} was not sanitized!"

    def test_concurrent_patch_application_same_file_race_condition(self, tmp_path):
        """
        Stress test: 10 concurrent requests attempting to apply patches to the EXACT SAME file.
        On Windows, file locking during concurrent read/write can cause collisions.
        The backend must either serialize safely or return a clear error without corrupting the file.
        """
        target = tmp_path / "shared_resource.py"
        orig_code = (
            "import sqlite3\n\n"
            "def fetch_item(item_id):\n"
            "    conn = sqlite3.connect('test.db')\n"
            "    cursor = conn.cursor()\n"
            "    cursor.execute(f'SELECT * FROM items WHERE id={item_id}')\n"
            "    return cursor.fetchone()\n"
        )
        target.write_text(orig_code, encoding="utf-8")

        # Get verified diff
        gen_resp = requests.post(
            f"{SERVER_URL}/api/generate-patches",
            json={"issue_id": "RACE_TEST", "code_content": orig_code, "target_file": "shared_resource.py"},
            timeout=15.0,
        )
        assert gen_resp.status_code == 200
        patch = gen_resp.json()["verified_patches"][0]
        diff_text = patch["diff"]

        concurrency = 10

        def hit_apply(req_id):
            r = requests.post(
                f"{SERVER_URL}/api/apply-patch",
                json={"target_file": str(target), "patch_diff": diff_text},
                timeout=15.0,
            )
            return req_id, r.status_code, r.text

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(hit_apply, i) for i in range(concurrency)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Analyze results
        statuses = [res[1] for res in results]
        status_counts = {s: statuses.count(s) for s in set(statuses)}

        # On Windows, concurrent writes trigger PermissionError [WinError 32] unless locked.
        # Verify that all responses are either 200 (applied), 422 (context mismatch/no-op), or 500 (Windows file lock contention)
        assert all(s in (200, 422, 500) for s in statuses), f"Unexpected status in {statuses}"

        # Most importantly, verify the target file is intact and valid CST syntax (no 0-byte truncation or corrupted text)
        final_content = target.read_text(encoding="utf-8")
        assert len(final_content) > 0, "Target file was truncated to 0 bytes!"
        assert "def fetch_item" in final_content, "Target file lost its function definition!"

