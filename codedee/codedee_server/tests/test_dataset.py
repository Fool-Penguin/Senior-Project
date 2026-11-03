"""
test_dataset.py - Unit tests for mini_test_datasets.json extraction and schema.

Validates:
1. Exact count of 105 CWE-89 samples.
2. Exact presence and order of the 14 required columns.
3. Language distribution (88 Python, 13 JavaScript, 4 TypeScript).
4. Data integrity, types, and presence of 5 curated benchmark gold standards.
"""

import json
from pathlib import Path
import pytest

from scripts.extract_dataset import REQUIRED_COLUMNS, extract_cwe89_dataset

DATASET_FILE = Path(__file__).resolve().parent.parent / "data" / "mini_test_datasets.json"


@pytest.fixture(scope="module")
def dataset_records():
    """Load extracted mini_test_datasets.json."""
    assert DATASET_FILE.exists(), f"Dataset file does not exist at {DATASET_FILE}"
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    return data


def test_dataset_record_count(dataset_records):
    """Verify exactly 105 records are extracted."""
    assert len(dataset_records) == 105, f"Expected 105 records, got {len(dataset_records)}"


def test_all_records_cwe_89(dataset_records):
    """Verify all extracted records have cwe_id == 'CWE-89'."""
    for r in dataset_records:
        assert r.get("cwe_id") == "CWE-89", f"Sample {r.get('sample_id')} has non-89 cwe_id: {r.get('cwe_id')}"
        assert r.get("cwe_name") == "SQL Injection"


def test_exact_14_columns_presence_and_order(dataset_records):
    """Verify all 105 records possess the exact 14 columns."""
    for idx, r in enumerate(dataset_records):
        keys = list(r.keys())
        assert keys == REQUIRED_COLUMNS, (
            f"Record {idx} ({r.get('sample_id')}) columns mismatch.\n"
            f"Expected: {REQUIRED_COLUMNS}\n"
            f"Got:      {keys}"
        )


def test_column_data_types(dataset_records):
    """Verify data types of all 14 columns across all records."""
    for r in dataset_records:
        # sample_id: non-empty str
        assert isinstance(r["sample_id"], str) and len(r["sample_id"].strip()) > 0
        # language: python, javascript, typescript
        assert r["language"] in ("python", "javascript", "typescript")
        # Is_vulnerable: bool
        assert isinstance(r["Is_vulnerable"], bool)
        # cwe_id: str
        assert r["cwe_id"] == "CWE-89"
        # cwe_name: str
        assert isinstance(r["cwe_name"], str) and len(r["cwe_name"]) > 0
        # cwe_description: str
        assert isinstance(r["cwe_description"], str) and len(r["cwe_description"]) > 10
        # owasp_category: str
        assert isinstance(r["owasp_category"], str) and "Injection" in r["owasp_category"]
        # cvss_v31_vector: str
        assert isinstance(r["cvss_v31_vector"], str) and r["cvss_v31_vector"].startswith("CVSS:3.1")
        # sources: str
        assert isinstance(r["sources"], str) and len(r["sources"]) > 0
        # original_code: str
        assert isinstance(r["original_code"], str) and len(r["original_code"]) > 0
        # fixed_code: str or None
        assert r["fixed_code"] is None or isinstance(r["fixed_code"], str)


def test_language_distribution(dataset_records):
    """Verify language breakdown: 88 Python, 13 JavaScript, 4 TypeScript."""
    py_count = sum(1 for r in dataset_records if r["language"] == "python")
    js_count = sum(1 for r in dataset_records if r["language"] == "javascript")
    ts_count = sum(1 for r in dataset_records if r["language"] == "typescript")

    assert py_count == 88, f"Expected 88 Python records, got {py_count}"
    assert js_count == 13, f"Expected 13 JavaScript records, got {js_count}"
    assert ts_count == 4, f"Expected 4 TypeScript records, got {ts_count}"
    assert py_count + js_count + ts_count == 105


def test_curated_benchmark_gold_standards(dataset_records):
    """Verify presence and fixed_code integrity of the 5 curated benchmark fixtures."""
    benchmarks = {
        "SEC_PY_CWE89_001": "python",
        "SEC_JS_CWE89_001": "javascript",
        "SEC_TS_JUICE_SHOP_001": "typescript",
        "SEC_PY_CVE_2023_34362": "python",
        "SEC_PY_PYGOAT_INJECTION_001": "python",
    }

    by_id = {r["sample_id"]: r for r in dataset_records}

    for sample_id, expected_lang in benchmarks.items():
        assert sample_id in by_id, f"Benchmark fixture {sample_id} missing from extracted dataset"
        record = by_id[sample_id]
        assert record["language"] == expected_lang
        assert record["fixed_code"] is not None and len(record["fixed_code"]) > 0
        assert len(record["original_code"]) > 0


def test_extractor_function_rerun(tmp_path):
    """Test programmatic extraction via extract_cwe89_dataset to temporary destination."""
    dest_temp = tmp_path / "test_mini.json"
    re_extracted = extract_cwe89_dataset(dest_path=dest_temp)
    assert len(re_extracted) == 105
    assert dest_temp.exists()
