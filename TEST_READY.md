# CodeDEE E2E Test Suite Readiness Report (`TEST_READY.md`)

**Date:** 2026-11-01  
**Author:** test_writer_e2e (E2E Testing Engineer)  
**Parent Orchestrator ID:** `cdd4c46b-fa83-40b4-992f-7161af706ca8`  
**Test Suite Path:** `d:\4th-year\Senior-Project\codedee\tests_e2e\`  
**Overall Status:** **100% READY & PASSING (74/74 Tests Passed)**  

---

## 1. Test Runner Command

To execute the entire CodeDEE E2E opaque-box test suite:

```powershell
python -m pytest -p no:anyio codedee/tests_e2e/ -v
```

To run individual tiers:

```powershell
# Tier 1: Feature Coverage (>=5 tests per feature)
python -m pytest -p no:anyio codedee/tests_e2e/test_tier1_features.py -v

# Tier 2: Boundary & Corner Cases (>=5 tests per feature)
python -m pytest -p no:anyio codedee/tests_e2e/test_tier2_boundaries.py -v

# Tier 3: Cross-Feature Combinations & Multi-Step Workflows
python -m pytest -p no:anyio codedee/tests_e2e/test_tier3_combinations.py -v

# Tier 4: Real-World CWE-89 Application Scenarios
python -m pytest -p no:anyio codedee/tests_e2e/test_tier4_real_world.py -v
```

---

## 2. Coverage Summary Table

| Tier | Focus Area | Target Count | Actual Tests | Passing | Failing | Pass Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Tier 1** | Feature Coverage (Happy Path) | $\ge 25$ | 28 | 28 | 0 | 100% |
| **Tier 2** | Boundary & Corner Cases | $\ge 25$ | 33 | 33 | 0 | 100% |
| **Tier 3** | Cross-Feature Interactions | $\ge 5$ | 7 | 7 | 0 | 100% |
| **Tier 4** | Real-World Application Scenarios | $\ge 5$ | 6 | 6 | 0 | 100% |
| **Total** | **Full Opaque-Box E2E Suite** | **$\ge 60$** | **74** | **74** | **0** | **100%** |

---

## 3. Feature Coverage Checklist

### Feature 1: Pre-Flight Health Check (`GET /health`)
- [x] Pre-flight status verification (HTTP 200/503)
- [x] Ollama daemon reachability flag verification
- [x] Required model identification (`qwen2.5-coder:7b`)
- [x] Backend server version specification (`1.0.0`)
- [x] Root endpoint (`/`) service directory listing
- [x] Endpoint alias compatibility (`/api/health`)
- [x] HTTP method guardrails (POST returns 405 Method Not Allowed)
- [x] Arbitrary query parameter tolerance
- [x] Rapid sequential query resilience

### Feature 2: Static Analysis & Security Audit (`POST /api/scan`)
- [x] Python source file scan on disk with CST parsing
- [x] JavaScript source file scan on disk with CST parsing
- [x] TypeScript source file scan on disk with CST parsing
- [x] In-memory virtual code content scan (editor buffer support)
- [x] Recursive multi-file directory scanning
- [x] ISO/IEC 25010 maintainability engine calculation (exactly 8 metrics):
  - Function-level: (1) CC, (2) Cognitive Complexity, (3) Parameter Count, (4) Function SLOC
  - File-level: (5) File SLOC, (6) Module Coupling Ce/Ca, (7) Duplicated Blocks, (8) Comment Density
- [x] Stage 3A Symbolic Taint Walker: taint source $\rightarrow$ propagation $\rightarrow$ SQL sink
- [x] Stage 3B Security Node Output Contract strict Pydantic compliance
- [x] Empty file (0-byte) and whitespace-only handling (0 issues, no crash)
- [x] Minimal single-statement parsing
- [x] Syntax error tolerance via Tree-sitter ERROR nodes
- [x] Non-existent target file path handling (HTTP 404)
- [x] Empty request payload validation (HTTP 400)
- [x] True-negative verification for parameterized queries (Python, JS, TS)
- [x] Safe handling of SQL keywords in strings and comments

### Feature 3: In-Memory Multi-Gate Patch Generation (`POST /api/generate-patches`)
- [x] Candidate patch generation via Ollama `qwen2.5-coder:7b` + rule transforms
- [x] Disk target file patch generation
- [x] In-memory code content patch generation
- [x] Direct sample_id resolution from `mini_test_datasets.json`
- [x] Candidate count parameter override (`candidate_count=3..4`)
- [x] Strict in-memory Multi-Gate verification:
  - Gate 1: Tree-sitter CST syntax validity check
  - Gate 2: Function name and parameter interface integrity check
  - Gate 3: SQL sink neutralization check (parameterized placeholder substitution)
  - Gate 4: Maintainability non-regression check ($\Delta CC \le 0$)
  - Gate 6: SAST re-scan check (0 active taint paths)
- [x] Pruning of non-conforming candidates (retaining only 100% verified patches)
- [x] Standard unified diff formatting for VS Code native diff provider
- [x] Non-existent issue_id/target_file handling (HTTP 404)
- [x] Missing mandatory field validation (HTTP 422)
- [x] Candidate count boundary validation (<1 or >5 returns 422)

### Feature 4: Safe Disk Patch Application (`POST /api/apply-patch`)
- [x] Remediated code substitution
- [x] Unified diff patch application
- [x] Automatic safety backup creation (`.bak`) containing original file content
- [x] Post-application Tree-sitter CST syntax verification
- [x] Rejection and automatic rollback when patch introduces syntax errors (HTTP 422)
- [x] Non-existent target file handling (HTTP 404)
- [x] Empty patch payload handling (HTTP 400)
- [x] Malformed unified diff resilience without file corruption
- [x] Pre-application backup preservation during rollbacks

### Feature 5: CWE-89 Dataset Extraction (`mini_test_datasets.json`)
- [x] File existence and valid JSON syntax
- [x] Exact 105 record count for `cwe_id == 'CWE-89'`
- [x] Strict 14 column schema compliance:
  `['sample_id', 'language', 'Is_vulnerable', 'cwe_id', 'cwe_name', 'cwe_description', 'owasp_category', 'cvss_v31_vector', 'sources', 'source_pattern', 'sink_pattern', 'sanitizer_pattern', 'original_code', 'fixed_code']`
- [x] Multi-language distribution (Python: 88, JavaScript: 13, TypeScript: 4)
- [x] Canonical CWE-89 descriptions and standard CVSS 3.1 vectors
- [x] Curated benchmark fixtures verification (`SEC_PY_CWE89_001`, `SEC_JS_CWE89_001`, `SEC_TS_JUICE_SHOP_001`)
- [x] Sample ID uniqueness and non-empty code strings

---

## 4. Test Suite Execution Log

```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Ongsa\miniconda3\python.exe
cachedir: .pytest_cache
rootdir: D:\4th-year\Senior-Project
collecting ... collected 74 items

codedee/tests_e2e/test_tier1_features.py::test_health_status_code_and_structure PASSED [  1%]
codedee/tests_e2e/test_tier1_features.py::test_health_ollama_reachability PASSED [  2%]
codedee/tests_e2e/test_tier1_features.py::test_health_model_availability PASSED [  4%]
codedee/tests_e2e/test_tier1_features.py::test_health_backend_version PASSED [  5%]
codedee/tests_e2e/test_tier1_features.py::test_health_alias_endpoint PASSED [  6%]
codedee/tests_e2e/test_tier1_features.py::test_health_root_endpoint_directory PASSED [  8%]
codedee/tests_e2e/test_tier1_features.py::test_scan_python_file_on_disk PASSED [  9%]
codedee/tests_e2e/test_tier1_features.py::test_scan_javascript_file_on_disk PASSED [ 10%]
codedee/tests_e2e/test_tier1_features.py::test_scan_typescript_file_on_disk PASSED [ 12%]
codedee/tests_e2e/test_tier1_features.py::test_scan_in_memory_code_content PASSED [ 13%]
codedee/tests_e2e/test_tier1_features.py::test_scan_maintainability_metrics_iso25010 PASSED [ 14%]
codedee/tests_e2e/test_tier1_features.py::test_scan_multi_file_directory PASSED [ 16%]
codedee/tests_e2e/test_tier1_features.py::test_generate_patches_with_code_content PASSED [ 17%]
codedee/tests_e2e/test_tier1_features.py::test_generate_patches_with_target_file PASSED [ 18%]
codedee/tests_e2e/test_tier1_features.py::test_generate_patches_dataset_match_by_issue_id PASSED [ 20%]
codedee/tests_e2e/test_tier1_features.py::test_generate_patches_candidate_count_override PASSED [ 21%]
codedee/tests_e2e/test_tier1_features.py::test_generate_patches_multi_gate_results PASSED [ 22%]
codedee/tests_e2e/test_tier1_features.py::test_apply_patch_with_remediated_code PASSED [ 24%]
codedee/tests_e2e/test_tier1_features.py::test_apply_patch_creates_backup_file PASSED [ 25%]
codedee/tests_e2e/test_tier1_features.py::test_apply_patch_with_unified_diff PASSED [ 27%]
codedee/tests_e2e/test_tier1_features.py::test_apply_patch_reverts_on_syntax_error PASSED [ 28%]
codedee/tests_e2e/test_tier1_features.py::test_apply_patch_response_schema PASSED [ 29%]
codedee/tests_e2e/test_tier1_features.py::test_dataset_file_exists_and_valid_json PASSED [ 31%]
codedee/tests_e2e/test_tier1_features.py::test_dataset_exact_count PASSED [ 32%]
codedee/tests_e2e/test_tier1_features.py::test_dataset_exact_14_columns PASSED [ 33%]
codedee/tests_e2e/test_tier1_features.py::test_dataset_multi_language_distribution PASSED [ 35%]
codedee/tests_e2e/test_tier1_features.py::test_dataset_canonical_cwe89_fields PASSED [ 36%]
codedee/tests_e2e/test_tier1_features.py::test_dataset_curated_benchmarks_present PASSED [ 37%]
codedee/tests_e2e/test_tier2_boundaries.py::test_health_post_method_not_allowed PASSED [ 39%]
codedee/tests_e2e/test_tier2_boundaries.py::test_health_query_parameters_tolerance PASSED [ 40%]
codedee/tests_e2e/test_tier2_boundaries.py::test_health_custom_accept_headers PASSED [ 41%]
codedee/tests_e2e/test_tier2_boundaries.py::test_health_root_post_rejected PASSED [ 43%]
codedee/tests_e2e/test_tier2_boundaries.py::test_health_rapid_sequential_queries PASSED [ 44%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_empty_code_content PASSED [ 45%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_whitespace_and_comments_only PASSED [ 47%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_single_line_minimal_code PASSED [ 48%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_huge_file_stress PASSED [ 50%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_syntax_error_file_graceful PASSED [ 51%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_non_existent_target_path PASSED [ 52%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_missing_both_target_and_content PASSED [ 54%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_python_non_vulnerable_parameterized PASSED [ 55%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_javascript_non_vulnerable_parameterized PASSED [ 56%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_typescript_non_vulnerable_orm PASSED [ 58%]
codedee/tests_e2e/test_tier2_boundaries.py::test_scan_sql_keywords_in_standard_strings_not_flagged PASSED [ 59%]
codedee/tests_e2e/test_tier2_boundaries.py::test_generate_patches_unknown_issue_and_target_file PASSED [ 60%]
codedee/tests_e2e/test_tier2_boundaries.py::test_generate_patches_missing_issue_id PASSED [ 62%]
codedee/tests_e2e/test_tier2_boundaries.py::test_generate_patches_candidate_count_underflow PASSED [ 63%]
codedee/tests_e2e/test_tier2_boundaries.py::test_generate_patches_candidate_count_overflow PASSED [ 64%]
codedee/tests_e2e/test_tier2_boundaries.py::test_generate_patches_empty_code_content PASSED [ 66%]
codedee/tests_e2e/test_tier2_boundaries.py::test_generate_patches_with_alias_num_candidates PASSED [ 67%]
codedee/tests_e2e/test_tier2_boundaries.py::test_apply_patch_non_existent_target_file PASSED [ 68%]
codedee/tests_e2e/test_tier2_boundaries.py::test_apply_patch_missing_both_remediated_and_diff PASSED [ 70%]
codedee/tests_e2e/test_tier2_boundaries.py::test_apply_patch_corrupt_unified_diff PASSED [ 71%]
codedee/tests_e2e/test_tier2_boundaries.py::test_apply_patch_reverts_syntax_error_javascript PASSED [ 72%]
codedee/tests_e2e/test_tier2_boundaries.py::test_apply_patch_backup_created_even_before_reversion PASSED [ 74%]
codedee/tests_e2e/test_tier2_boundaries.py::test_dataset_sample_ids_are_unique PASSED [ 75%]
codedee/tests_e2e/test_tier2_boundaries.py::test_dataset_original_code_non_empty PASSED [ 77%]
codedee/tests_e2e/test_tier2_boundaries.py::test_dataset_is_vulnerable_is_boolean PASSED [ 78%]
codedee/tests_e2e/test_tier2_boundaries.py::test_dataset_cvss_vector_format_regex PASSED [ 79%]
codedee/tests_e2e/test_tier2_boundaries.py::test_dataset_languages_lowercase_standard PASSED [ 81%]
codedee/tests_e2e/test_tier2_boundaries.py::test_dataset_fixed_code_syntax_validity PASSED [ 82%]
codedee/tests_e2e/test_tier3_combinations.py::test_combination_python_full_repair_cycle PASSED [ 83%]
codedee/tests_e2e/test_tier3_combinations.py::test_combination_javascript_full_repair_cycle PASSED [ 85%]
codedee/tests_e2e/test_tier3_combinations.py::test_combination_typescript_full_repair_cycle PASSED [ 86%]
codedee/tests_e2e/test_tier3_combinations.py::test_combination_health_gated_multi_file_directory_remediation PASSED [ 87%]
codedee/tests_e2e/test_tier3_combinations.py::test_combination_unsafe_patch_rejection_and_rollback PASSED [ 89%]
codedee/tests_e2e/test_tier3_combinations.py::test_combination_in_memory_virtual_repair_pipeline PASSED [ 90%]
codedee/tests_e2e/test_tier3_combinations.py::test_combination_maintainability_non_regression_across_repair PASSED [ 91%]
codedee/tests_e2e/test_tier4_real_world.py::test_scenario_sec_py_cwe89_001_sqlite_login PASSED [ 93%]
codedee/tests_e2e/test_tier4_real_world.py::test_scenario_sec_js_cwe89_001_pg_client PASSED [ 94%]
codedee/tests_e2e/test_tier4_real_world.py::test_scenario_sec_ts_juice_shop_001_sequelize PASSED [ 95%]
codedee/tests_e2e/test_tier4_real_world.py::test_scenario_sec_py_cve_2023_34362_moveit PASSED [ 97%]
codedee/tests_e2e/test_tier4_real_world.py::test_scenario_sec_py_pygoat_injection_001 PASSED [ 98%]
codedee/tests_e2e/test_tier4_real_world.py::test_scenario_bulk_dataset_scan_sampling PASSED [100%]

======================= 74 passed, 6 warnings in 26.38s =======================
```
