import json
import math

dataset_path = r"D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json"

with open(dataset_path, "r", encoding="utf-8") as f:
    data = json.load(f)

cwe89 = [r for r in data if r.get("cwe_id") == "CWE-89"]

print(f"Total CWE-89 records: {len(cwe89)}")

# Let's inspect unique values across all 17 keys for CWE-89
keys = list(cwe89[0].keys())
print("All keys present in CWE-89 records:")
for k in keys:
    val_types = set(type(r.get(k)).__name__ for r in cwe89)
    # Check non-null/non-empty
    non_null_count = sum(1 for r in cwe89 if r.get(k) is not None and not (isinstance(r.get(k), float) and math.isnan(r.get(k))))
    print(f"  {k}: types={val_types}, non-null count={non_null_count}/{len(cwe89)}")

# Print 2 samples across different languages (python, javascript, typescript)
for lang in ['python', 'javascript', 'typescript']:
    matching = [r for r in cwe89 if r.get('language') == lang]
    if matching:
        print(f"\n================ Sample for {lang} ================")
        s = matching[0]
        for k, v in s.items():
            if k in ['code', 'fixed_code']:
                print(f"  {k}: length {len(str(v))} chars | preview: {repr(str(v)[:100])}")
            else:
                print(f"  {k}: {repr(v)}")
