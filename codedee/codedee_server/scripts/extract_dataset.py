"""
extract_dataset.py - Extracts CWE-89 SQL Injection mini test datasets.

Filters D:\\4th-year\\Senior-Project\\datasets\\unified\\codedee_security_dataset_catalogue_scope.json
for `cwe_id == 'CWE-89'` and produces `codedee_server/data/mini_test_datasets.json`
with exactly 105 samples and the exact 14 columns required by CodeDEE specification.
"""

import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Default paths
DEFAULT_SOURCE_PATH = Path(r"D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json")
DEFAULT_DEST_PATH = Path(__file__).resolve().parent.parent / "data" / "mini_test_datasets.json"

CWE_89_CANONICAL_DESC = (
    "The software constructs all or part of an SQL command using externally-influenced input "
    "from an upstream component, but it does not neutralize or incorrectly neutralizes "
    "special elements that could modify the intended SQL command when it is sent to a downstream component."
)

CVSS_V31_DEFAULT_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"

REQUIRED_COLUMNS: List[str] = [
    "sample_id",
    "language",
    "Is_vulnerable",
    "cwe_id",
    "cwe_name",
    "cwe_description",
    "owasp_category",
    "cvss_v31_vector",
    "sources",
    "source_pattern",
    "sink_pattern",
    "sanitizer_pattern",
    "original_code",
    "fixed_code",
]


def clean_val(v: Any) -> Optional[Any]:
    """Clean NaN and null values."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str) and v.strip() in ("", "NaN", "nan", "None", "null"):
        return None
    return v


def extract_cwe89_dataset(
    source_path: Path = DEFAULT_SOURCE_PATH,
    dest_path: Path = DEFAULT_DEST_PATH,
) -> List[Dict[str, Any]]:
    """Extract CWE-89 samples and write to dest_path."""
    if not source_path.exists():
        raise FileNotFoundError(f"Source dataset not found at: {source_path}")

    with open(source_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    if not isinstance(raw_data, list):
        raise ValueError(f"Expected JSON list in {source_path}, got {type(raw_data)}")

    # Filter for CWE-89
    cwe89_raw = [r for r in raw_data if r.get("cwe_id") == "CWE-89"]

    output_records: List[Dict[str, Any]] = []
    for r in cwe89_raw:
        record: Dict[str, Any] = {
            "sample_id": r.get("sample_id"),
            "language": str(r.get("language", "")).lower(),
            "Is_vulnerable": bool(r.get("is_vulnerable", True)),
            "cwe_id": r.get("cwe_id", "CWE-89"),
            "cwe_name": r.get("cwe_name", "SQL Injection"),
            "cwe_description": clean_val(r.get("cwe_description")) or CWE_89_CANONICAL_DESC,
            "owasp_category": r.get("owasp_category", "A03:2021-Injection"),
            "cvss_v31_vector": clean_val(r.get("cvss_v31_vector")) or CVSS_V31_DEFAULT_VECTOR,
            "sources": r.get("source_dataset") or r.get("sources", "CodeDEE Unified Catalogue"),
            "source_pattern": clean_val(r.get("source_pattern")),
            "sink_pattern": clean_val(r.get("sink_pattern")),
            "sanitizer_pattern": clean_val(r.get("sanitizer_pattern")),
            "original_code": r.get("code", ""),
            "fixed_code": clean_val(r.get("fixed_code")),
        }

        # Verify exact columns order and presence
        if list(record.keys()) != REQUIRED_COLUMNS:
            raise ValueError(f"Column mismatch in record {record.get('sample_id')}")

        output_records.append(record)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(output_records, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(output_records)} CWE-89 records to {dest_path}")
    return output_records


if __name__ == "__main__":
    records = extract_cwe89_dataset()
    print(f"Extraction successful: {len(records)} samples processed.")
