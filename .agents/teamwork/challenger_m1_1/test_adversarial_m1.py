"""
test_adversarial_m1.py - Empirical Adversarial Test Suite for Milestone 1.

Challenge Areas:
1. Schema Validation Stress Tests:
   - Corrupted records, missing required fields, illegal values, out-of-bound ranges.
2. API Endpoints Input Robustness & Error Handling:
   - Malformed JSON, empty inputs, non-existent target files.
   - Malicious patch strings, corrupted unified diffs, path traversal attempts.
   - Code with syntax errors during scan and patch generation.
   - Silent no-op vulnerability on bogus diffs in /api/apply-patch.
3. Health Endpoint Error Handling:
   - Ollama connection refused (socket error), timeout, missing model, HTTP 500 from Ollama.
4. Dataset Extraction Integrity & Corruption Resistance:
   - Integrity of all 105 samples (types, non-empty, uniqueness).
   - Analysis of synthetic / meta prompts without explicit SQL keywords.
   - Corruption resistance of extract_dataset.py against missing columns and invalid formats.
5. In-Memory Multi-Gate Verifier Adversarial Stress Tests:
   - Gate 2 signature order assumption (helper function prepending).
   - Gate 3 & Gate 6 partial parameterization bypass vulnerability.
   - Gate 4 CC regression detection.
6. C-level Memory / GC Stress Boundary Condition:
   - Tree-sitter AST Node allocation GC pressure under Python 3.14 on Windows.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import requests
from fastapi.testclient import TestClient
from pydantic import ValidationError

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.main import app
from app.models.contracts import (
    ApplyPatchRequest,
    CodeLocation,
    GeneratePatchesRequest,
    HealthCheckResponse,
    MaintainabilityMetrics,
    NeuroAssessment,
    PipelineMetadata,
    ScanRequest,
    SecurityNodeOutput,
    SymbolicFinding,
    TaintStep,
    VerifiedPatch,
)
from app.api.patches import (
    verify_gate_1_syntax,
    verify_gate_2_interface,
    verify_gate_3_taint_neutralized,
    verify_gate_4_maintainability,
    verify_gate_6_sast_rescan,
)
from app.api.apply import apply_unified_diff
from scripts.extract_dataset import REQUIRED_COLUMNS, extract_cwe89_dataset

client = TestClient(app)


# ============================================================================
# 1. Schema Validation Adversarial Tests
# ============================================================================

class TestSchemaValidationAdversarial:
    """Stress tests and boundary condition verification for Pydantic contracts."""

    def test_security_node_output_missing_mandatory_fields(self):
        """Verify ValidationError when mandatory fields are omitted."""
        corrupted_data = {
            "issue_id": "ISSUE-01",
        }
        with pytest.raises(ValidationError) as exc_info:
            SecurityNodeOutput.model_validate(corrupted_data)
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "target_file" in field_names
        assert "symbolic_finding" in field_names
        assert "pipeline_metadata" in field_names

    def test_neuro_assessment_confidence_out_of_bounds(self):
        """Verify confidence_score strictly enforces [0.0, 1.0]."""
        base_data = {
            "risk_level": "HIGH",
            "sanitizer_detected": False,
            "reasoning": "Valid reasoning string",
        }
        with pytest.raises(ValidationError):
            NeuroAssessment.model_validate({**base_data, "confidence_score": -0.1})

        with pytest.raises(ValidationError):
            NeuroAssessment.model_validate({**base_data, "confidence_score": 1.01})

        with pytest.raises(ValidationError):
            NeuroAssessment.model_validate({**base_data, "confidence_score": "not-a-number"})

    def test_maintainability_metrics_negative_values(self):
        """Verify maintainability metrics reject negative values where ge=0 or ge=1."""
        with pytest.raises(ValidationError):
            MaintainabilityMetrics(cyclomatic_complexity=0)

        with pytest.raises(ValidationError):
            MaintainabilityMetrics(cognitive_complexity=-5)

        with pytest.raises(ValidationError):
            MaintainabilityMetrics(comment_density=1.5)

    def test_code_location_invalid_line(self):
        """Verify CodeLocation rejects non-positive line numbers."""
        with pytest.raises(ValidationError):
            CodeLocation(file="test.py", line=0)

        with pytest.raises(ValidationError):
            CodeLocation(file="test.py", line=-10)

    def test_generate_patches_request_candidate_count_bounds(self):
        """Verify candidate_count bounds (ge=1, le=5)."""
        with pytest.raises(ValidationError):
            GeneratePatchesRequest(issue_id="ISSUE-01", candidate_count=0)

        with pytest.raises(ValidationError):
            GeneratePatchesRequest(issue_id="ISSUE-01", candidate_count=6)

    def test_reconcile_nodes_and_aliases(self):
        """Verify backward/forward compatibility aliases work as designed."""
        data = {
            "cwe_id": "CWE-89",
            "cwe_name": "SQL Injection",
            "severity": "HIGH",
            "source": {"file": "a.py", "line": 10, "symbol": "id"},
            "sink": {"file": "a.py", "line": 20, "symbol": "execute"},
        }
        finding = SymbolicFinding.model_validate(data)
        assert finding.source_node["symbol"] == "id"
        assert finding.sink_node["symbol"] == "execute"


# ============================================================================
# 2. API Endpoints Input Robustness & Error Handling
# ============================================================================

class TestApiEndpointsAdversarial:
    """Adversarial stress-testing of FastAPI routes."""

    def test_scan_empty_json_body(self):
        """Verify POST /api/scan rejects empty payload with 400 Bad Request."""
        res = client.post("/api/scan", json={})
        assert res.status_code == 400
        assert "Either target_path or code_content must be provided" in res.json()["detail"]

    def test_scan_invalid_json(self):
        """Verify POST /api/scan handles raw invalid JSON with 422."""
        res = client.post(
            "/api/scan",
            content="NOT_VALID_JSON{:::}",
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 422

    def test_scan_non_existent_target_path(self):
        """Verify POST /api/scan returns 404 for nonexistent path."""
        res = client.post("/api/scan", json={"target_path": "Z:\\this\\does\\not\\exist_12345.py"})
        assert res.status_code == 404
        assert "Target path not found" in res.json()["detail"]

    def test_scan_syntax_broken_code_buffer(self):
        """Verify POST /api/scan does not crash on syntactically broken code."""
        broken_code = "def ((;; invalid python syntax ??? :::\n\t\t@@@\n\n"
        res = client.post(
            "/api/scan",
            json={"code_content": broken_code, "language": "python", "file_name": "broken.py"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"

    def test_scan_empty_string_code_buffer(self):
        """Verify POST /api/scan handles completely empty string."""
        res = client.post(
            "/api/scan",
            json={"code_content": "", "language": "python", "file_name": "empty.py"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["issues_count"] == 0
        assert data["maintainability"]["file_sloc"] >= 1

    def test_scan_moderate_large_input_buffer(self):
        """Verify POST /api/scan handles buffer with 100 comment lines."""
        code = "# Comment line\n" * 100 + "def foo():\n    return 42\n"
        res = client.post(
            "/api/scan",
            json={"code_content": code, "language": "python", "file_name": "large.py"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["maintainability"]["comment_density"] > 0.9

    def test_generate_patches_missing_issue_id(self):
        """Verify POST /api/generate-patches rejects missing issue_id with 422."""
        res = client.post("/api/generate-patches", json={"target_file": "sample.py"})
        assert res.status_code == 422

    def test_generate_patches_unresolvable_issue(self):
        """Verify POST /api/generate-patches returns 404 when code cannot be resolved."""
        res = client.post(
            "/api/generate-patches",
            json={"issue_id": "NON_EXISTENT_ISSUE_999999", "target_file": "missing.py"},
        )
        assert res.status_code == 404
        assert "Could not locate vulnerable code" in res.json()["detail"]

    def test_generate_patches_with_ollama_failure_fallback(self):
        """Verify patch generation falls back to rule-based candidates if Ollama is unreachable."""
        vuln_code = (
            "def query_user(request):\n"
            "    user_id = request.args.get('id')\n"
            "    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
            "    return cursor.fetchall()\n"
        )
        with patch("requests.post", side_effect=requests.ConnectionError("Ollama down")):
            res = client.post(
                "/api/generate-patches",
                json={
                    "issue_id": "TEST_FALLBACK_01",
                    "code_content": vuln_code,
                    "target_file": "user_query.py",
                    "candidate_count": 3,
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert data["verified_count"] >= 1
            for p in data["verified_patches"]:
                assert "cursor.execute" in p["remediated_code"]
                assert "?" in p["remediated_code"]

    def test_apply_patch_nonexistent_target_file(self):
        """Verify POST /api/apply-patch returns 404 for missing target file."""
        res = client.post(
            "/api/apply-patch",
            json={
                "target_file": "C:\\nonexistent\\path\\sample.py",
                "remediated_code": "def foo(): pass",
            },
        )
        assert res.status_code == 404
        assert "Target file does not exist" in res.json()["detail"]

    def test_apply_patch_empty_payload(self):
        """Verify POST /api/apply-patch rejects missing remediated_code & patch_diff."""
        temp_file = SERVER_ROOT / "tests" / "_temp_target.py"
        try:
            temp_file.write_text("x = 1\n", encoding="utf-8")
            res = client.post("/api/apply-patch", json={"target_file": str(temp_file)})
            assert res.status_code == 400
            assert "Either remediated_code or patch_diff must be supplied" in res.json()["detail"]
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_apply_patch_malicious_unified_diff_corrupt_hunk(self, tmp_path):
        """Verify POST /api/apply-patch with corrupt unified diff does not corrupt target file."""
        orig_content = "def calculate(a, b):\n    return a + b\n"
        target_file = tmp_path / "math_ops.py"
        target_file.write_text(orig_content, encoding="utf-8")

        corrupt_diff = (
            "--- a/math_ops.py\n"
            "+++ b/math_ops.py\n"
            "@@ -INVALID_HUNK_HEADER @@\n"
            "+def broken(\n"
        )
        res = client.post(
            "/api/apply-patch",
            json={"target_file": str(target_file), "patch_diff": corrupt_diff},
        )
        assert res.status_code == 422
        assert target_file.read_text(encoding="utf-8") == orig_content

    def test_apply_patch_atomic_rollback_on_syntax_error(self, tmp_path):
        """Verify rollback occurs when candidate patch has invalid syntax."""
        target_file = tmp_path / "target_rollback.py"
        target_file.write_text("def hello():\n    print('hello')\n", encoding="utf-8")

        bad_patch = "def hello():\n    syntax error !! $$$ @"
        res = client.post(
            "/api/apply-patch",
            json={"target_file": str(target_file), "remediated_code": bad_patch},
        )
        assert res.status_code == 422
        assert "invalid CST syntax" in res.json()["detail"]
        assert target_file.read_text(encoding="utf-8") == "def hello():\n    print('hello')\n"

    def test_apply_patch_silent_noop_on_bogus_diff(self, tmp_path):
        """
        FINDING: Bogus diff string without @@ hunk headers returns 200 without modifying code.
        Documents silent no-op vulnerability in diff parsing.
        """
        orig_content = "def foo():\n    return 1\n"
        target_file = tmp_path / "target_bogus.py"
        target_file.write_text(orig_content, encoding="utf-8")

        res = client.post(
            "/api/apply-patch",
            json={"target_file": str(target_file), "patch_diff": "totally bogus diff string with no hunks"},
        )
        # Server accepts it because apply_unified_diff ignores lines outside hunks
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        # But the content was essentially unchanged!
        assert "def foo():" in target_file.read_text(encoding="utf-8")


# ============================================================================
# 3. Health Endpoint Error Handling
# ============================================================================

class TestHealthEndpointAdversarial:
    """Adversarial testing of GET /health under failure scenarios."""

    def test_health_ollama_connection_refused(self):
        """Verify 503 response when Ollama port is closed / connection refused."""
        with patch("requests.get", side_effect=requests.ConnectionError("Connection refused")):
            res = client.get("/health")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "unhealthy"
            assert data["ollama_reachable"] is False
            assert data["model_available"] is False

    def test_health_ollama_timeout(self):
        """Verify 503 response when Ollama times out."""
        with patch("requests.get", side_effect=requests.Timeout("Request timed out")):
            res = client.get("/health")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "unhealthy"
            assert data["ollama_reachable"] is False
            assert data["model_available"] is False

    def test_health_ollama_missing_required_model(self):
        """Verify 503 degraded response when Ollama is up but model is missing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3:latest"}, {"name": "mistral:7b"}]
        }
        with patch("requests.get", return_value=mock_response):
            res = client.get("/health")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "degraded"
            assert data["ollama_reachable"] is True
            assert data["model_available"] is False
            assert "llama3:latest" in data["available_models"]

    def test_health_ollama_500_internal_error(self):
        """Verify 503 response when Ollama returns 500."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("requests.get", return_value=mock_response):
            res = client.get("/health")
            assert res.status_code == 503
            data = res.json()
            assert data["ollama_reachable"] is False
            assert data["model_available"] is False


# ============================================================================
# 4. Dataset Extraction & Integrity Check
# ============================================================================

class TestDatasetIntegrityAdversarial:
    """Rigorous dataset verification for all 105 samples and extraction robustness."""

    @pytest.fixture(scope="class")
    def dataset(self):
        dataset_path = SERVER_ROOT / "data" / "mini_test_datasets.json"
        assert dataset_path.exists(), f"Dataset not found at {dataset_path}"
        with open(dataset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_exact_105_samples(self, dataset):
        """Verify exactly 105 samples."""
        assert len(dataset) == 105

    def test_unique_sample_ids(self, dataset):
        """Verify every sample_id is unique across all 105 records."""
        ids = [r["sample_id"] for r in dataset]
        assert len(ids) == len(set(ids)), f"Duplicate sample_ids found: {len(ids) - len(set(ids))} duplicates"

    def test_mandatory_fields_non_empty(self, dataset):
        """Verify every record has non-empty values for all strictly required fields."""
        mandatory_fields = [
            "sample_id",
            "language",
            "Is_vulnerable",
            "cwe_id",
            "cwe_name",
            "cwe_description",
            "owasp_category",
            "cvss_v31_vector",
            "sources",
            "original_code",
        ]
        for idx, r in enumerate(dataset):
            for field in mandatory_fields:
                val = r.get(field)
                assert val is not None, f"Record {idx} ({r.get('sample_id')}) field '{field}' is None"
                if isinstance(val, str):
                    assert len(val.strip()) > 0, f"Record {idx} ({r.get('sample_id')}) field '{field}' is empty string"

    def test_valid_languages_only(self, dataset):
        """Verify languages are strictly constrained to python, javascript, typescript."""
        valid_languages = {"python", "javascript", "typescript"}
        for r in dataset:
            assert r["language"] in valid_languages, f"Unexpected language: {r['language']}"

    def test_sql_keywords_presence_analysis(self, dataset):
        """
        Verify that >= 90% of records contain explicit SQL keywords.
        Identifies and documents the 9 synthetic / meta prompt records that lack direct keywords.
        """
        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "QUERY", "EXECUTE", "SQL", "FROM", "WHERE"]
        with_sql = [r for r in dataset if any(kw in r["original_code"].upper() for kw in sql_keywords)]
        without_sql = [r for r in dataset if not any(kw in r["original_code"].upper() for kw in sql_keywords)]

        # 96 / 105 (91.4%) contain explicit SQL keywords
        assert len(with_sql) >= 95, f"Only {len(with_sql)}/105 contain SQL keywords"

        # The 9 non-SQL records are known edge cases from META or raw snippets:
        non_sql_ids = [r["sample_id"] for r in without_sql]
        assert len(non_sql_ids) == 9
        assert "META_1606" in non_sql_ids

    def test_extractor_rejects_non_list_source(self, tmp_path):
        """Verify extract_cwe89_dataset raises ValueError if root is not a list."""
        corrupted_source = tmp_path / "corrupt_dict.json"
        corrupted_source.write_text(json.dumps({"error": "not a list"}), encoding="utf-8")

        dest_file = tmp_path / "output.json"
        with pytest.raises(ValueError) as exc:
            extract_cwe89_dataset(source_path=corrupted_source, dest_path=dest_file)
        assert "Expected JSON list" in str(exc.value)

    def test_extractor_rejects_nonexistent_source(self):
        """Verify FileNotFoundError if source dataset path does not exist."""
        with pytest.raises(FileNotFoundError):
            extract_cwe89_dataset(source_path=Path("nonexistent_catalogue.json"))


# ============================================================================
# 5. In-Memory Multi-Gate Verifier Adversarial Stress Tests
# ============================================================================

class TestMultiGateVerifierAdversarial:
    """Stress-tests targeting Gate 1, Gate 2, Gate 3, Gate 4, and Gate 6."""

    def test_gate_2_false_rejection_on_helper_function(self):
        """
        FINDING: Gate 2 falsely fails when a candidate patch prepends a helper function.
        Logic flaw: Gate 2 compares orig_sigs[0] with cand_sigs[0].
        """
        orig_code = "def query_db(user_id):\n    cursor.execute(user_id)\n"
        cand_code = "def _sanitize(x):\n    return int(x)\n\ndef query_db(user_id):\n    cursor.execute('SELECT ?', (_sanitize(user_id),))\n"
        res = verify_gate_2_interface(orig_code, cand_code, "python")
        # Demonstrates that Gate 2 naively flags function name mismatch from 'query_db' to '_sanitize'
        assert res.passed is False
        assert "Function name changed from 'query_db' to '_sanitize'" in res.details

    def test_partial_parameterization_bypass_in_gate_3_and_6(self):
        """
        FINDING: Partial parameterization bypass in Gate 3 and Gate 6.
        When code mixes dangerous string concatenation with parameter placeholders,
        e.g. cursor.execute("SELECT ... " + untrusted + " WHERE id = %s", (id,))
        Gate 3 and Gate 6 falsely pass because of naive regex detection of ', ('.
        """
        # Code that still has active SQL injection via string concatenation '+'
        cand_code = "cursor.execute('SELECT * FROM users WHERE name = ' + user_input + ' AND id = %s', (valid_id,))"

        g3 = verify_gate_3_taint_neutralized("orig", cand_code, "python")
        g6 = verify_gate_6_sast_rescan(cand_code, "python")

        # Both gates incorrectly pass due to regex-based sanitization check
        assert g3.passed is True
        assert g6.passed is True

    def test_gate_4_catches_complexity_spike(self):
        """Verify Gate 4 correctly catches cyclomatic complexity increases."""
        orig_code = "def process(x):\n    return x * 2\n"
        cand_code = (
            "def process(x):\n"
            "    if x > 10:\n"
            "        for i in range(x):\n"
            "            if i % 2 == 0:\n"
            "                x += 1\n"
            "    return x\n"
        )
        res, delta_cc = verify_gate_4_maintainability(orig_code, cand_code, "python")
        assert res.passed is False
        assert delta_cc > 0
        assert "regression" in res.details


# ============================================================================
# 6. C-level Memory / GC Stress Boundary Condition
# ============================================================================

class TestTreeSitterMemoryStressBoundary:
    """Stress test verifying Python 3.14 GC stability under high AST node creation."""

    def test_tree_sitter_ast_node_gc_boundary(self):
        """
        FINDING: Large repetitive ASTs (500+ comments) traversed via node.children
        trigger Windows fatal exception access violation in Python 3.14 garbage collector.
        Verified in subprocess to avoid crashing test runner.
        """
        sub_code = (
            "import sys; sys.path.insert(0, r'" + str(SERVER_ROOT) + "'); "
            "from app.api.scan import get_parser_for_language, compute_maintainability_metrics; "
            "p = get_parser_for_language('python'); "
            "code = '# Comment\\n' * 500 + 'def foo():\\n    return 42\\n'; "
            "m = compute_maintainability_metrics(code, 'python', p.parse(code.encode())); "
            "import gc; gc.collect()"
        )
        proc = subprocess.run([sys.executable, "-X", "faulthandler", "-c", sub_code], capture_output=True, text=True)
        # Returns exit code 1 or 3221225477 (0xC0000005) with Windows fatal exception: access violation
        is_crashed = proc.returncode != 0 and ("access violation" in proc.stderr.lower() or proc.returncode in (1, 3221225477, -1073741819))
        assert is_crashed, f"Expected GC access violation on 500 comment nodes, but process exited with {proc.returncode}"
