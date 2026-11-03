import json
import math

dataset_path = r"D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json"

with open(dataset_path, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

cwe89_raw = [r for r in raw_data if r.get("cwe_id") == "CWE-89"]

def sanitize_val(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v

CWE_89_CANONICAL_DESC = (
    "The software constructs all or part of an SQL command using externally-influenced input "
    "from an upstream component, but it does not neutralize or incorrectly neutralizes "
    "special elements that could modify the intended SQL command when it is sent to a downstream component."
)

CVSS_V31_DEFAULT_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"

extracted_records = []
for r in cwe89_raw:
    # 14 columns
    record = {
        "sample_id": r.get("sample_id"),
        "language": r.get("language"),
        "Is_vulnerable": bool(r.get("is_vulnerable", True)),
        "cwe_id": r.get("cwe_id", "CWE-89"),
        "cwe_name": r.get("cwe_name", "SQL Injection"),
        "cwe_description": sanitize_val(r.get("cwe_description")) or CWE_89_CANONICAL_DESC,
        "owasp_category": r.get("owasp_category", "A03:2021-Injection"),
        "cvss_v31_vector": sanitize_val(r.get("cvss_v31_vector")) or CVSS_V31_DEFAULT_VECTOR,
        "sources": r.get("source_dataset") or r.get("sources", "CodeDEE Unified Catalogue"),
        "source_pattern": sanitize_val(r.get("source_pattern")),
        "sink_pattern": sanitize_val(r.get("sink_pattern")),
        "sanitizer_pattern": sanitize_val(r.get("sanitizer_pattern")),
        "original_code": r.get("code", ""),
        "fixed_code": sanitize_val(r.get("fixed_code"))
    }
    extracted_records.append(record)

print(f"Extracted {len(extracted_records)} CWE-89 records.")
print("Columns for first record:", list(extracted_records[0].keys()))
print("All 14 columns matched:", list(extracted_records[0].keys()) == [
    "sample_id", "language", "Is_vulnerable", "cwe_id", "cwe_name",
    "cwe_description", "owasp_category", "cvss_v31_vector", "sources",
    "source_pattern", "sink_pattern", "sanitizer_pattern", "original_code", "fixed_code"
])
