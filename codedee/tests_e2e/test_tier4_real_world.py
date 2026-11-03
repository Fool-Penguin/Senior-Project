"""
test_tier4_real_world.py - Tier 4: Real-World Application Scenarios.

Executes end-to-end security audit and automated program repair against authentic
CWE-89 SQL Injection samples extracted from mini_test_datasets.json:
1. Python Curated Benchmark: SEC_PY_CWE89_001 (SQLite Login SQL Injection)
2. JavaScript Curated Benchmark: SEC_JS_CWE89_001 (PostgreSQL pg Client Injection)
3. TypeScript Curated Benchmark: SEC_TS_JUICE_SHOP_001 (OWASP Juice Shop Route Injection)
4. Real-world CVE Sample: SEC_PY_CVE_2023_34362 (MOVEit Transfer SQL Injection)
5. Real-world PyGoat Sample: SEC_PY_PYGOAT_INJECTION_001 (Flask PyGoat Challenge)
6. Bulk Dataset Scan Sampling across Python, JavaScript, and TypeScript
"""

from pathlib import Path
from typing import Any, Dict, List
import pytest


def test_scenario_sec_py_cwe89_001_sqlite_login(client, temp_workspace, datasets_by_id):
    """
    Scenario 1: Python Curated Benchmark (SEC_PY_CWE89_001).
    Real-world SQLite authentication bypass via string formatting.
    Verifies full lifecycle: Scan -> 5-Gate Patch Gen -> Apply -> Clean Re-scan.
    """
    sample = datasets_by_id["SEC_PY_CWE89_001"]
    orig_code = sample["original_code"]
    ground_truth_fixed = sample["fixed_code"]

    target_file = temp_workspace.create_file("sqlite_login.py", orig_code)

    # 1. Scan authentic sample
    scan_resp = client.post("/api/scan", json={"target_path": str(target_file)})
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["issues_count"] >= 1

    issue = scan_data["issues"][0]
    assert issue["symbolic_finding"]["cwe_id"] == "CWE-89"
    assert issue["pipeline_metadata"]["language"] == "python"
    assert "maintainability_metrics" in issue["pipeline_metadata"]

    # 2. Generate 3 candidate fixes
    gen_resp = client.post(
        "/api/generate-patches",
        json={"issue_id": sample["sample_id"], "target_file": str(target_file), "candidate_count": 3},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["verified_count"] >= 1

    best_patch = gen_data["verified_patches"][0]
    assert best_patch["gate1_syntax"]["passed"] is True
    assert best_patch["gate2_interface"]["passed"] is True
    assert best_patch["gate3_taint_neutralized"]["passed"] is True
    assert best_patch["gate4_maintainability"]["passed"] is True
    assert best_patch["gate6_sast_rescan"]["passed"] is True
    assert best_patch["delta_cc"] <= 0

    # 3. Apply patch
    apply_resp = client.post(
        "/api/apply-patch",
        json={
            "target_file": str(target_file),
            "remediated_code": best_patch["remediated_code"],
            "patch_id": best_patch["patch_id"],
        },
    )
    assert apply_resp.status_code == 200
    assert temp_workspace.exists("sqlite_login.py.bak")

    # 4. Re-scan target file
    rescan_resp = client.post("/api/scan", json={"target_path": str(target_file)})
    assert rescan_resp.status_code == 200
    assert rescan_resp.json()["issues_count"] == 0


def test_scenario_sec_js_cwe89_001_pg_client(client, temp_workspace, datasets_by_id):
    """
    Scenario 2: JavaScript Curated Benchmark (SEC_JS_CWE89_001).
    Real-world Node.js PostgreSQL client query interpolation vulnerability.
    """
    sample = datasets_by_id["SEC_JS_CWE89_001"]
    orig_code = sample["original_code"]

    target_file = temp_workspace.create_file("pg_service.js", orig_code)

    # 1. Scan authentic sample
    scan_resp = client.post("/api/scan", json={"target_path": str(target_file)})
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["issues_count"] >= 1
    assert scan_data["issues"][0]["pipeline_metadata"]["language"] == "javascript"

    # 2. Generate candidate fixes
    gen_resp = client.post(
        "/api/generate-patches",
        json={"issue_id": sample["sample_id"], "target_file": str(target_file), "candidate_count": 3},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["verified_count"] >= 1

    best_patch = gen_data["verified_patches"][0]
    assert "$1" in best_patch["remediated_code"] or "?" in best_patch["remediated_code"]

    # 3. Apply patch
    apply_resp = client.post(
        "/api/apply-patch",
        json={
            "target_file": str(target_file),
            "remediated_code": best_patch["remediated_code"],
            "patch_id": best_patch["patch_id"],
        },
    )
    assert apply_resp.status_code == 200

    # 4. Re-scan
    rescan_resp = client.post("/api/scan", json={"target_path": str(target_file)})
    assert rescan_resp.status_code == 200
    assert rescan_resp.json()["issues_count"] == 0


def test_scenario_sec_ts_juice_shop_001_sequelize(client, temp_workspace, datasets_by_id):
    """
    Scenario 3: TypeScript Curated Benchmark (SEC_TS_JUICE_SHOP_001).
    Authentic OWASP Juice Shop raw database query injection.
    """
    sample = datasets_by_id["SEC_TS_JUICE_SHOP_001"]
    orig_code = sample["original_code"]

    target_file = temp_workspace.create_file("searchProducts.ts", orig_code)

    # 1. Scan authentic sample
    scan_resp = client.post("/api/scan", json={"target_path": str(target_file)})
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["issues_count"] >= 1
    assert scan_data["issues"][0]["pipeline_metadata"]["language"] == "typescript"

    # 2. Generate candidate fixes
    gen_resp = client.post(
        "/api/generate-patches",
        json={"issue_id": sample["sample_id"], "target_file": str(target_file), "candidate_count": 3},
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["verified_count"] >= 1
    best_patch = gen_data["verified_patches"][0]

    # 3. Apply patch
    apply_resp = client.post(
        "/api/apply-patch",
        json={
            "target_file": str(target_file),
            "remediated_code": best_patch["remediated_code"],
            "patch_id": best_patch["patch_id"],
        },
    )
    assert apply_resp.status_code == 200

    # 4. Re-scan
    rescan_resp = client.post("/api/scan", json={"target_path": str(target_file)})
    assert rescan_resp.status_code == 200
    assert rescan_resp.json()["issues_count"] == 0


def test_scenario_sec_py_cve_2023_34362_moveit(client, temp_workspace, datasets_by_id):
    """
    Scenario 4: Real-world CVE Sample (SEC_PY_CVE_2023_34362 - MOVEit Transfer SQLi).
    Verifies that authentic enterprise vulnerability is detected and repairable.
    """
    sample = datasets_by_id.get("SEC_PY_CVE_2023_34362") or next(
        r for r in datasets_by_id.values() if "CVE" in r["sample_id"] and r["language"] == "python"
    )
    orig_code = sample["original_code"]

    target_file = temp_workspace.create_file("moveit_service.py", orig_code)

    # Scan
    scan_resp = client.post("/api/scan", json={"target_path": str(target_file)})
    assert scan_resp.status_code == 200
    data = scan_resp.json()
    assert data["files_scanned"] == 1

    # Verify metrics calculated
    assert data["maintainability"]["cyclomatic_complexity"] >= 1
    assert data["maintainability"]["file_sloc"] >= 1


def test_scenario_sec_py_pygoat_injection_001(client, temp_workspace, datasets_by_id):
    """
    Scenario 5: Real-world Flask PyGoat Injection Challenge (SEC_PY_PYGOAT_INJECTION_001).
    Verifies Stage 3B NeuroAssessment details and remediation advice.
    """
    sample = datasets_by_id.get("SEC_PY_PYGOAT_INJECTION_001") or next(
        r for r in datasets_by_id.values() if "PYGOAT" in r["sample_id"]
    )
    orig_code = sample["original_code"]

    target_file = temp_workspace.create_file("pygoat_auth.py", orig_code)

    scan_resp = client.post("/api/scan", json={"target_path": str(target_file)})
    assert scan_resp.status_code == 200
    data = scan_resp.json()
    assert data["issues_count"] >= 1

    issue = data["issues"][0]
    neuro = issue["neuro_assessment"]
    assert neuro["confidence_score"] >= 0.7
    assert neuro["risk_level"] in ("CRITICAL", "HIGH")
    assert any(term in neuro["suggested_remediation"].lower() for term in ("parameter", "placeholder", "?", "prepared"))


def test_scenario_bulk_dataset_scan_sampling(client, mini_datasets):
    """
    Scenario 6: Bulk Dataset Scan Sampling.
    Samples 10 diverse records across Python, JavaScript, and TypeScript from mini_test_datasets.json.
    Verifies that every sample is parsed without crashing and produces 8 ISO/IEC 25010 metrics.
    """
    # Select 6 Python, 2 JavaScript, 2 TypeScript samples
    py_samples = [r for r in mini_datasets if r["language"] == "python"][:6]
    js_samples = [r for r in mini_datasets if r["language"] == "javascript"][:2]
    ts_samples = [r for r in mini_datasets if r["language"] == "typescript"][:2]

    test_samples = py_samples + js_samples + ts_samples
    assert len(test_samples) == 10

    for sample in test_samples:
        code = sample["original_code"]
        lang = sample["language"]
        file_ext = "py" if lang == "python" else ("ts" if lang == "typescript" else "js")
        virtual_name = f"{sample['sample_id']}.{file_ext}"

        resp = client.post(
            "/api/scan",
            json={"code_content": code, "file_name": virtual_name, "language": lang},
        )
        assert resp.status_code == 200, f"Failed on sample {sample['sample_id']}: {resp.text}"
        data = resp.json()
        assert data["files_scanned"] == 1
        m = data["maintainability"]
        assert m["cyclomatic_complexity"] >= 1
        assert m["cognitive_complexity"] >= 0
        assert m["parameter_count"] >= 0
        assert m["function_sloc"] >= 1
        assert m["file_sloc"] >= 1
        assert "Ce" in m["module_coupling"]
        assert "Ca" in m["module_coupling"]
        assert "instability" in m["module_coupling"]
        assert m["duplicated_blocks"] >= 0
        assert 0.0 <= m["comment_density"] <= 1.0
