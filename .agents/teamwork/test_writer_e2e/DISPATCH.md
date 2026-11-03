# Dispatch for E2E Test Writer
Dual Track E2E Testing: Test infrastructure and Tiers 1-4 test cases based on ORIGINAL_REQUEST.md and PROJECT.md.
See prompt for full details.
## 2026-11-01T09:03:24Z
Sender: cdd4c46b-fa83-40b4-992f-7161af706ca8
Priority: MESSAGE_PRIORITY_HIGH
Content:
You are test_writer_e2e, the E2E Testing Engineer for CodeDEE.
Your working directory is: d:\4th-year\Senior-Project\.agents\teamwork\test_writer_e2e
You MUST read the original request file first: d:\4th-year\Senior-Project\.agents\teamwork\ORIGINAL_REQUEST.md
Also read the project architecture document: d:\4th-year\Senior-Project\.agents\teamwork\orchestrator\PROJECT.md

Your mission is the Dual Track E2E Testing Track:
1. Design comprehensive opaque-box test infrastructure derived from user requirements and specifications.
   - Use the 4-tier testing methodology:
     - Tier 1: Feature Coverage (>=5 tests per feature)
     - Tier 2: Boundary & Corner Cases (>=5 tests per feature)
     - Tier 3: Cross-Feature Combinations (pairwise coverage of major feature interactions)
     - Tier 4: Real-World Application Scenarios (real CWE-89 vulnerable samples across Python, JavaScript, and TypeScript from mini_test_datasets.json)
2. Create test files under `d:\4th-year\Senior-Project\codedee\tests_e2e\`:
   - `conftest.py` / test fixtures (pointing to API server at http://127.0.0.1:8000 or in-memory TestClient).
   - `test_tier1_features.py`: Happy path tests for /health, /api/scan, /api/generate-patches, /api/apply-patch, and dataset extraction.
   - `test_tier2_boundaries.py`: Malformed inputs, empty files, huge files, syntax error files, non-vulnerable files.
   - `test_tier3_combinations.py`: Cross-feature interactions (scan -> generate patches -> apply patch -> re-scan).
   - `test_tier4_real_world.py`: Realistic end-to-end scenarios executing against Python, JS, and TS SQL Injection samples.
3. Write `d:\4th-year\Senior-Project\TEST_INFRA.md` at project root using the standard template:
   - Test philosophy, feature inventory, test architecture, real-world scenarios, coverage thresholds.
4. When the test suite is complete and runnable via pytest, publish `d:\4th-year\Senior-Project\TEST_READY.md` documenting:
   - Test runner command: how to run full test suite.
   - Coverage summary table (Tier 1, 2, 3, 4 counts).
   - Feature checklist.
5. Provide a full handoff report in `d:\4th-year\Senior-Project\.agents\teamwork\test_writer_e2e\handoff.md`.
6. Send a message to your parent orchestrator when complete.
