"""
test_tier3_combinations.py - Tier 3: Cross-Feature Combinations.

Pairwise and multi-stage workflow integration tests covering:
1. Full Python Repair Cycle (Scan -> Generate Patches -> Apply Patch -> Re-Scan -> 0 Flaws)
2. Full JavaScript Repair Cycle (Scan -> Generate Patches -> Apply Patch -> Re-Scan -> 0 Flaws)
3. Full TypeScript Repair Cycle (Scan -> Generate Patches -> Apply Patch -> Re-Scan -> 0 Flaws)
4. Health-Gated Multi-File Directory Batch Scan & Staged Remediation
5. Unsafe Patch Rejection & Automatic Safety Rollback to Backup
6. In-Memory Virtual Repair Pipeline (Zero Disk Mutation)
7. Maintainability Non-Regression Verification Across Repair Cycle (Delta CC <= 0)
"""

from pathlib import Path
import pytest


def test_combination_python_full_repair_cycle(client, temp_workspace):
    """
    Combination 1: Full Python End-to-End Cycle.
    1. Scan vulnerable file -> detect CWE-89
    2. Generate patches -> get multi-gate verified patch
    3. Apply patch -> update target file on disk with backup
    4. Re-scan file -> verify issues_count == 0
    """
    orig_code = (
        "import sqlite3\n"
        "from flask import request\n\n"
        "def user_login():\n"
        "    uname = request.args.get('user')\n"
        "    conn = sqlite3.connect('database.db')\n"
        "    cursor = conn.cursor()\n"
        "    return cursor.execute(f\"SELECT * FROM users WHERE username = '{uname}'\").fetchall()\n"
    )
    target = temp_workspace.create_file("app_auth.py", orig_code)

    # Step 1: Scan
    scan_resp = client.post("/api/scan", json={"target_path": str(target)})
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["issues_count"] >= 1
    issue = scan_data["issues"][0]
    issue_id = issue["issue_id"]

    # Step 2: Generate Patches
    gen_resp = client.post(
        "/api/generate-patches",
        json={"issue_id": issue_id, "target_file": str(target), "candidate_count": 3},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["verified_count"] >= 1
    best_patch = gen_data["verified_patches"][0]
    assert best_patch["remediated_code"] != orig_code
    assert best_patch["delta_cc"] <= 0

    # Step 3: Apply Patch
    apply_resp = client.post(
        "/api/apply-patch",
        json={
            "target_file": str(target),
            "remediated_code": best_patch["remediated_code"],
            "patch_id": best_patch["patch_id"],
        },
    )
    assert apply_resp.status_code == 200
    apply_data = apply_resp.json()
    assert apply_data["success"] is True
    assert temp_workspace.exists("app_auth.py.bak")

    # Step 4: Re-scan
    rescan_resp = client.post("/api/scan", json={"target_path": str(target)})
    assert rescan_resp.status_code == 200
    rescan_data = rescan_resp.json()
    assert rescan_data["issues_count"] == 0, f"Expected 0 issues after patch, found {rescan_data['issues_count']}"


def test_combination_javascript_full_repair_cycle(client, temp_workspace):
    """
    Combination 2: Full JavaScript End-to-End Cycle.
    1. Scan vulnerable JS file -> detect CWE-89
    2. Generate patches -> get parameterized $1 fix
    3. Apply patch -> update target file
    4. Re-scan -> verify issues_count == 0
    """
    orig_code = (
        "const { Client } = require('pg');\n\n"
        "async function fetchAccount(req, res) {\n"
        "    const client = new Client();\n"
        "    await client.connect();\n"
        "    const email = req.query.email;\n"
        "    const result = await client.query(`SELECT * FROM accounts WHERE email = '${email}'`);\n"
        "    return res.json(result.rows);\n"
        "}\n"
    )
    target = temp_workspace.create_file("account.js", orig_code)

    # Step 1: Scan
    scan_resp = client.post("/api/scan", json={"target_path": str(target)})
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["issues_count"] >= 1
    issue_id = scan_data["issues"][0]["issue_id"]

    # Step 2: Generate Patches
    gen_resp = client.post(
        "/api/generate-patches",
        json={"issue_id": issue_id, "target_file": str(target), "candidate_count": 3},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["verified_count"] >= 1
    best_patch = gen_data["verified_patches"][0]

    # Step 3: Apply Patch
    apply_resp = client.post(
        "/api/apply-patch",
        json={
            "target_file": str(target),
            "remediated_code": best_patch["remediated_code"],
            "patch_id": best_patch["patch_id"],
        },
    )
    assert apply_resp.status_code == 200

    # Step 4: Re-scan
    rescan_resp = client.post("/api/scan", json={"target_path": str(target)})
    assert rescan_resp.status_code == 200
    assert rescan_resp.json()["issues_count"] == 0


def test_combination_typescript_full_repair_cycle(client, temp_workspace):
    """
    Combination 3: Full TypeScript End-to-End Cycle.
    1. Scan vulnerable TS file -> detect CWE-89
    2. Generate patches -> get verified parameterized candidate
    3. Apply patch -> verify disk write
    4. Re-scan -> verify clean state
    """
    orig_code = (
        "export function searchItems(criteria: string, db: any) {\n"
        "    return db.query(`SELECT * FROM Items WHERE name LIKE '%${criteria}%'`);\n"
        "}\n"
    )
    target = temp_workspace.create_file("search.ts", orig_code)

    # Step 1: Scan
    scan_resp = client.post("/api/scan", json={"target_path": str(target)})
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["issues_count"] >= 1
    issue_id = scan_data["issues"][0]["issue_id"]

    # Step 2: Generate Patches
    gen_resp = client.post(
        "/api/generate-patches",
        json={"issue_id": issue_id, "target_file": str(target), "candidate_count": 3},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["verified_count"] >= 1
    best_patch = gen_data["verified_patches"][0]

    # Step 3: Apply Patch
    apply_resp = client.post(
        "/api/apply-patch",
        json={
            "target_file": str(target),
            "remediated_code": best_patch["remediated_code"],
            "patch_id": best_patch["patch_id"],
        },
    )
    assert apply_resp.status_code == 200

    # Step 4: Re-scan
    rescan_resp = client.post("/api/scan", json={"target_path": str(target)})
    assert rescan_resp.status_code == 200
    assert rescan_resp.json()["issues_count"] == 0


def test_combination_health_gated_multi_file_directory_remediation(client, temp_workspace):
    """
    Combination 4: Health-Gated Multi-File Directory Batch Scan & Staged Remediation.
    1. Check /health
    2. Scan project dir with 2 vulnerable files and 1 clean file
    3. Remediate file 1, verify issue count decrements by 1
    4. Remediate file 2, verify issue count reaches 0
    """
    # 1. Health check pre-flight
    h_resp = client.get("/health")
    assert h_resp.status_code in (200, 503)

    # 2. Setup multi-file project
    py_code = "def f(u): return cursor.execute(f'SELECT * FROM u WHERE id={u}')"
    js_code = "function g(u) { return db.query(`SELECT * FROM g WHERE id=${u}`); }"
    clean_code = "export function safe(x: number): number { return x * 2; }"

    f_py = temp_workspace.create_file("proj/v1.py", py_code)
    f_js = temp_workspace.create_file("proj/v2.js", js_code)
    f_ts = temp_workspace.create_file("proj/clean.ts", clean_code)

    proj_dir = str(temp_workspace.root / "proj")

    # Initial directory scan
    scan1 = client.post("/api/scan", json={"target_path": proj_dir}).json()
    assert scan1["files_scanned"] == 3
    assert scan1["issues_count"] == 2

    # Repair file 1 (Python)
    patch1 = client.post(
        "/api/generate-patches",
        json={"issue_id": "P1", "target_file": str(f_py), "candidate_count": 3},
    ).json()["verified_patches"][0]
    client.post("/api/apply-patch", json={"target_file": str(f_py), "remediated_code": patch1["remediated_code"]})

    # Intermediate scan: issues must be 1
    scan2 = client.post("/api/scan", json={"target_path": proj_dir}).json()
    assert scan2["issues_count"] == 1

    # Repair file 2 (JavaScript)
    patch2 = client.post(
        "/api/generate-patches",
        json={"issue_id": "P2", "target_file": str(f_js), "candidate_count": 3},
    ).json()["verified_patches"][0]
    client.post("/api/apply-patch", json={"target_file": str(f_js), "remediated_code": patch2["remediated_code"]})

    # Final scan: issues must be 0
    scan3 = client.post("/api/scan", json={"target_path": proj_dir}).json()
    assert scan3["issues_count"] == 0


def test_combination_unsafe_patch_rejection_and_rollback(client, temp_workspace):
    """
    Combination 5: Unsafe Patch Rejection & Automatic Safety Rollback.
    1. Scan vulnerable file -> detect flaw
    2. Attempt to apply invalid patch with syntax error
    3. Endpoint rejects with 422
    4. Target file is restored intact from backup
    5. Re-scan confirms original flaw is still present and file uncorrupted
    """
    code = "def query(val):\n    return cursor.execute('SELECT ' + val)\n"
    target = temp_workspace.create_file("safe_check.py", code)

    # Verify initial scan flags flaw
    scan_init = client.post("/api/scan", json={"target_path": str(target)}).json()
    assert scan_init["issues_count"] == 1

    # Submit corrupted patch
    broken_patch = "def query(val):\n    return return <<<< broken syntax\n"
    apply_resp = client.post(
        "/api/apply-patch",
        json={"target_file": str(target), "remediated_code": broken_patch},
    )
    assert apply_resp.status_code == 422

    # Verify target file is still original content
    assert target.read_text(encoding="utf-8") == code

    # Re-scan confirms original flaw is intact and server does not crash
    scan_after = client.post("/api/scan", json={"target_path": str(target)}).json()
    assert scan_after["issues_count"] == 1


def test_combination_in_memory_virtual_repair_pipeline(client):
    """
    Combination 6: In-Memory Virtual Repair Pipeline (Zero Disk I/O).
    1. Scan code_content in memory
    2. Generate patches for code_content in memory
    3. Verify verified patch neutralizes taint without writing to disk
    """
    mem_code = "def get_order(order_id):\n    return cursor.execute(f\"SELECT * FROM orders WHERE id = '{order_id}'\")\n"

    # Step 1: Scan
    scan_res = client.post(
        "/api/scan",
        json={"code_content": mem_code, "file_name": "virtual_order.py", "language": "python"},
    ).json()
    assert scan_res["issues_count"] == 1

    # Step 2: Generate Patches
    gen_res = client.post(
        "/api/generate-patches",
        json={"issue_id": "MEM_ISSUE_01", "code_content": mem_code, "candidate_count": 3},
    ).json()
    assert gen_res["verified_count"] >= 1
    remediated = gen_res["verified_patches"][0]["remediated_code"]

    # Step 3: Virtual Re-scan
    rescan_res = client.post(
        "/api/scan",
        json={"code_content": remediated, "file_name": "virtual_order.py", "language": "python"},
    ).json()
    assert rescan_res["issues_count"] == 0


def test_combination_maintainability_non_regression_across_repair(client, temp_workspace):
    """
    Combination 7: Maintainability Non-Regression Across Repair Cycle.
    Verifies that the applied fix preserves or improves cyclomatic complexity (Delta CC <= 0).
    """
    orig_code = (
        "def evaluate_query(user_id):\n"
        "    if user_id > 0:\n"
        "        return cursor.execute(f\"SELECT * FROM data WHERE uid = '{user_id}'\")\n"
        "    return None\n"
    )
    target = temp_workspace.create_file("maintain.py", orig_code)

    # Initial Maintainability
    m_before = client.post("/api/scan", json={"target_path": str(target)}).json()["maintainability"]
    cc_before = m_before["cyclomatic_complexity"]

    # Generate and apply patch
    patches = client.post(
        "/api/generate-patches",
        json={"issue_id": "M_TEST", "target_file": str(target), "candidate_count": 3},
    ).json()
    assert patches["verified_count"] >= 1
    best = patches["verified_patches"][0]
    assert best["delta_cc"] <= 0

    client.post("/api/apply-patch", json={"target_file": str(target), "remediated_code": best["remediated_code"]})

    # Post-repair Maintainability
    m_after = client.post("/api/scan", json={"target_path": str(target)}).json()["maintainability"]
    cc_after = m_after["cyclomatic_complexity"]

    assert cc_after <= cc_before, f"Cyclomatic complexity regressed from {cc_before} to {cc_after}"
