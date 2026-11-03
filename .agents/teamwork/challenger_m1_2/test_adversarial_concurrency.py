"""
Adversarial Test Suite 3: Concurrency & Load Stress Testing.
Tests backend robustness under concurrent traffic:
1. 50 concurrent requests to GET /health (checking for socket exhaustion, race conditions).
2. 32 concurrent requests to POST /api/scan with mixed Python/JS/TS code payloads.
3. Concurrency safety of Tree-sitter parsers and NetworkX graph builders.
4. Concurrent mixed load: GET /health + POST /api/scan + POST /api/apply-patch.
"""

import sys
import time
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest
from fastapi.testclient import TestClient

# Add codedee_server to path
server_root = Path(r"d:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(server_root))

from app.main import app

client = TestClient(app)

# -----------------------------------------------------------------------------
# 1. Concurrency: GET /health (50 concurrent threads)
# -----------------------------------------------------------------------------

def test_concurrent_health_checks():
    """
    Stress test: 50 concurrent GET /health requests.
    Verifies thread safety, response consistency, and Ollama check stability.
    """
    num_requests = 50
    results = []

    def make_health_request(req_id):
        start = time.perf_counter()
        resp = client.get("/health")
        duration = time.perf_counter() - start
        return req_id, resp.status_code, resp.json(), duration

    start_total = time.perf_counter()
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_health_request, i) for i in range(num_requests)]
        for f in as_completed(futures):
            results.append(f.result())
    total_time = time.perf_counter() - start_total

    status_codes = [r[1] for r in results]
    durations = [r[3] for r in results]

    assert all(code == 200 for code in status_codes), f"Some health checks failed: {status_codes}"
    avg_latency = sum(durations) / len(durations)
    print(f"\n[CONCURRENCY /health] {num_requests} requests in {total_time:.3f}s. Avg latency: {avg_latency*1000:.1f}ms, Max: {max(durations)*1000:.1f}ms")

# -----------------------------------------------------------------------------
# 2. Concurrency: POST /api/scan (32 concurrent AST / Taint analyses)
# -----------------------------------------------------------------------------

def test_concurrent_scan_multilingual():
    """
    Stress test: 32 concurrent scans across Python, JavaScript, and TypeScript payloads.
    Verifies that Tree-sitter parsers and maintainability metrics do not suffer from
    race conditions or cross-request state contamination.
    """
    payloads = [
        # Vulnerable Python
        {
            "code_content": "def get_user(uid):\n    query = f'SELECT * FROM users WHERE id = {uid}'\n    cursor.execute(query)\n",
            "file_name": "vuln.py",
            "language": "python",
            "expect_vuln": True,
        },
        # Safe Python
        {
            "code_content": "def get_user(uid):\n    query = 'SELECT * FROM users WHERE id = %s'\n    cursor.execute(query, (uid,))\n",
            "file_name": "safe.py",
            "language": "python",
            "expect_vuln": False,
        },
        # Vulnerable JavaScript
        {
            "code_content": "function findItem(req, res) {\n    const query = `SELECT * FROM items WHERE name = ${req.query.item}`;\n    db.query(query);\n}\n",
            "file_name": "vuln.js",
            "language": "javascript",
            "expect_vuln": True,
        },
        # Vulnerable TypeScript
        {
            "code_content": "export function searchDoc(req: any, res: any) {\n    const query = `SELECT * FROM docs WHERE q = '${req.params.term}'`;\n    client.query(query);\n}\n",
            "file_name": "vuln.ts",
            "language": "typescript",
            "expect_vuln": True,
        },
    ]

    # Generate 32 requests (8 repetitions of the 4 payloads)
    test_cases = payloads * 8
    results = []

    def make_scan_request(case_id, payload):
        start = time.perf_counter()
        resp = client.post("/api/scan", json={
            "code_content": payload["code_content"],
            "file_name": payload["file_name"],
            "language": payload["language"],
        })
        duration = time.perf_counter() - start
        return case_id, resp.status_code, resp.json() if resp.status_code == 200 else None, duration, payload["expect_vuln"]

    start_total = time.perf_counter()
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(make_scan_request, i, test_cases[i]) for i in range(len(test_cases))]
        for f in as_completed(futures):
            results.append(f.result())
    total_time = time.perf_counter() - start_total

    # Verify all succeeded with 200
    for case_id, code, data, duration, expect_vuln in results:
        assert code == 200, f"Scan request {case_id} failed with status {code}"
        assert data["status"] == "completed"
        if expect_vuln:
            assert data["issues_count"] >= 1, f"Expected vulnerability in case {case_id}, got {data['issues_count']}"
            assert len(data["issues"]) >= 1
            # Verify issue structure
            issue = data["issues"][0]
            assert "issue_id" in issue
            assert issue["symbolic_finding"]["cwe_id"] == "CWE-89"
        else:
            assert data["issues_count"] == 0, f"Expected safe code in case {case_id}, got {data['issues_count']}"

    durations = [r[3] for r in results]
    avg_latency = sum(durations) / len(durations)
    print(f"\n[CONCURRENCY /api/scan] {len(test_cases)} concurrent scans in {total_time:.3f}s. Avg latency: {avg_latency*1000:.1f}ms, Max: {max(durations)*1000:.1f}ms")

# -----------------------------------------------------------------------------
# 3. Mixed Concurrent Workload (Health + Scan + Apply)
# -----------------------------------------------------------------------------

def test_concurrent_mixed_workload():
    """
    Stress test: Mixed concurrent load combining GET /health, POST /api/scan,
    and POST /api/apply-patch targeting isolated temporary files.
    """
    temp_files = []
    try:
        # Create 10 temporary files for apply-patch and close them properly for Windows
        for i in range(10):
            tf = tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8")
            tf.write(f"def task_{i}():\n    return {i}\n")
            tf.flush()
            tf.close()
            temp_files.append(tf.name)

        tasks = []
        # 15 health checks
        for i in range(15):
            tasks.append(("health", i, None))
        # 15 scans
        for i in range(15):
            tasks.append(("scan", i, {
                "code_content": f"def test_{i}(p):\n    query = f'SELECT * FROM tbl WHERE id = {{p}}'\n    return db.query(query)\n",
                "file_name": f"test_{i}.py",
                "language": "python",
            }))
        # 10 patch applications
        for i, tf_path in enumerate(temp_files):
            tasks.append(("apply", i, {
                "target_file": tf_path,
                "remediated_code": f"def task_{i}():\n    # patched\n    return {i * 10}\n",
                "patch_id": f"MIXED_PATCH_{i}",
            }))

        results = []

        def execute_task(task_type, task_id, payload):
            if task_type == "health":
                r = client.get("/health")
                return task_type, task_id, r.status_code
            elif task_type == "scan":
                r = client.post("/api/scan", json=payload)
                return task_type, task_id, r.status_code
            elif task_type == "apply":
                r = client.post("/api/apply-patch", json=payload)
                return task_type, task_id, r.status_code

        start_time = time.perf_counter()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(execute_task, t[0], t[1], t[2]) for t in tasks]
            for f in as_completed(futures):
                results.append(f.result())
        total_time = time.perf_counter() - start_time

        # All tasks must return 200
        for task_type, task_id, status_code in results:
            assert status_code == 200, f"Task {task_type}_{task_id} failed with {status_code}"

        print(f"\n[CONCURRENCY mixed workload] {len(tasks)} mixed requests executed in {total_time:.3f}s. 100% success.")

    finally:
        for p_str in temp_files:
            p = Path(p_str)
            p.unlink(missing_ok=True)
            Path(p_str + ".bak").unlink(missing_ok=True)

if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
