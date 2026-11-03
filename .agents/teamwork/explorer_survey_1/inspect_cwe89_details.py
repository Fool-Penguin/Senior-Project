import json
import math

dataset_path = r"D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json"

with open(dataset_path, "r", encoding="utf-8") as f:
    data = json.load(f)

cwe89 = [r for r in data if r.get("cwe_id") == "CWE-89"]

print(f"Total CWE-89 records: {len(cwe89)}")

# Check fixed_code availability
has_fixed = [r for r in cwe89 if r.get("fixed_code") and isinstance(r.get("fixed_code"), str) and len(r.get("fixed_code").strip()) > 0]
print(f"Records with valid fixed_code: {len(has_fixed)}")
for lang in ['python', 'javascript', 'typescript']:
    count_total = sum(1 for r in cwe89 if r.get('language') == lang)
    count_fixed = sum(1 for r in has_fixed if r.get('language') == lang)
    print(f"  {lang}: {count_total} total, {count_fixed} have fixed_code")

# Check source_pattern and sink_pattern
for lang in ['python', 'javascript', 'typescript']:
    matching = [r for r in cwe89 if r.get('language') == lang]
    print(f"\n--- {lang} patterns check ---")
    for r in matching[:3]:
        print(f"  Sample ID: {r.get('sample_id')}")
        print(f"    Source pattern: {r.get('source_pattern')}")
        print(f"    Sink pattern: {r.get('sink_pattern')}")
        print(f"    Sanitizer pattern: {r.get('sanitizer_pattern')}")
        print(f"    Source dataset: {r.get('source_dataset')}")
        print(f"    Expected CVSS: {r.get('expected_cvss')}")
        print(f"    Code snippet (first 60 chars): {repr(r.get('code')[:60])}")
        print(f"    Fixed code snippet (first 60 chars): {repr(str(r.get('fixed_code'))[:60])}")

# Let's inspect all 4 typescript samples
print("\n--- All TypeScript CWE-89 Samples ---")
for r in [r for r in cwe89 if r.get('language') == 'typescript']:
    print(f"Sample ID: {r.get('sample_id')}")
    print(f"  Is vulnerable: {r.get('is_vulnerable')}")
    print(f"  Has fixed code: {bool(r.get('fixed_code'))}")
    print(f"  Code: {repr(r.get('code')[:80])}")
    print(f"  Fixed: {repr(str(r.get('fixed_code'))[:80])}")
