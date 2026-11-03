import json
import os
from collections import Counter

dataset_path = r"D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json"

if not os.path.exists(dataset_path):
    print(f"Error: {dataset_path} does not exist.")
    exit(1)

size_bytes = os.path.getsize(dataset_path)
print(f"File size: {size_bytes} bytes ({size_bytes / (1024*1024):.2f} MB)")

with open(dataset_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Root JSON type: {type(data)}")
if isinstance(data, list):
    print(f"Total records in dataset: {len(data)}")
    first_record = data[0] if data else {}
    print(f"Sample record keys ({len(first_record)} keys):", list(first_record.keys()))
elif isinstance(data, dict):
    print(f"Root keys: {list(data.keys())}")
    # Inspect internal structures
    for k, v in data.items():
        if isinstance(v, list):
            print(f"Key '{k}' is list of length {len(v)}")
            if v:
                print(f"  First item keys: {list(v[0].keys()) if isinstance(v[0], dict) else type(v[0])}")

# Let's inspect records
records = data if isinstance(data, list) else data.get("records", data.get("samples", []))

# Filter CWE-89
cwe_89_records = []
all_cwes = Counter()
all_langs = Counter()
cwe_89_langs = Counter()

expected_14_cols = [
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
    "fixed_code"
]

col_presence = {col: 0 for col in expected_14_cols}
other_keys = set()

for r in records:
    cwe = r.get("cwe_id")
    lang = r.get("language")
    all_cwes[cwe] += 1
    all_langs[lang] += 1
    if cwe == "CWE-89":
        cwe_89_records.append(r)
        cwe_89_langs[lang] += 1
        for col in expected_14_cols:
            if col in r:
                col_presence[col] += 1
        for k in r.keys():
            if k not in expected_14_cols:
                other_keys.add(k)

print("\n--- CWE-89 Analysis ---")
print(f"Total CWE-89 samples: {len(cwe_89_records)}")
print("CWE-89 language distribution:", dict(cwe_89_langs))
print("All languages across dataset:", dict(all_langs))
print("Top 10 CWEs:", all_cwes.most_common(10))

print("\n--- 14 Column Verification on CWE-89 samples ---")
for col in expected_14_cols:
    print(f"  {col}: present in {col_presence[col]}/{len(cwe_89_records)} samples")

print("Other keys in CWE-89 records:", list(other_keys))

if cwe_89_records:
    sample = cwe_89_records[0]
    print("\nSample 1 preview:")
    for k in expected_14_cols:
        val = sample.get(k)
        val_str = str(val)[:80] + ("..." if len(str(val)) > 80 else "")
        print(f"  {k} ({type(val).__name__}): {val_str}")
