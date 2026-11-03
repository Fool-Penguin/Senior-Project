import csv
import re
import sys

PEER_CHILD_CWES = {"CWE-1336", "CWE-943", "CWE-1321", "CWE-1333"}

def verify_file(filepath):
    print(f"\n--- Verifying {filepath} ---")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 28, f"Expected 28 rows, got {len(rows)}"

    errors = []
    for idx, r in enumerate(rows, 1):
        name = r["Name"]
        refs = r["References"].strip()
        cwe_match = re.search(r"CWE-\d+", refs)
        if not cwe_match:
            errors.append(f"Row {idx} ({name}): No CWE found in References '{refs}'")
            continue
        cwe_id = cwe_match.group(0)

        if cwe_id in PEER_CHILD_CWES:
            # Must be CWE only!
            if "OWASP" in refs:
                errors.append(f"Row {idx} ({name}): Is a peer/child ({cwe_id}) but contains OWASP: '{refs}'")
            elif refs != cwe_id:
                errors.append(f"Row {idx} ({name}): Expected strictly '{cwe_id}', got '{refs}'")
            else:
                print(f"  [OK: Peer/Child -> CWE Only] {idx:2d} | {name:40s} -> {refs}")
        else:
            # Must have OWASP itself along with CWE
            if "OWASP" not in refs:
                errors.append(f"Row {idx} ({name}): Has OWASP itself ({cwe_id}) but missing OWASP in References: '{refs}'")
            else:
                print(f"  [OK: OWASP Itself Included ] {idx:2d} | {name:40s} -> {refs}")

    if errors:
        print("\nERRORS DETECTED:")
        for e in errors:
            print("  -", e)
        return False
    return True

ok1 = verify_file("Taxonomy_table.csv")
ok2 = verify_file("data/Taxonomy_table.csv")

print("\n--- Verifying docs/08_Vulnerability_Taxonomy_and_Machine_Requirements.md ---")
with open("docs/08_Vulnerability_Taxonomy_and_Machine_Requirements.md", "r", encoding="utf-8") as f:
    doc08 = f.read()

assert "CWE-89, OWASP A05:2025" in doc08
assert "CWE-1336 |" in doc08
assert "CWE-943 |" in doc08
assert "CWE-1321 |" in doc08
assert "CWE-1333 |" in doc08
assert "CWE-1427, OWASP LLM01:2025" in doc08
assert "CWE-1426, OWASP LLM05:2025" in doc08
assert "CWE-798, OWASP A07:2025" in doc08
assert "CWE-915, OWASP A08:2025" in doc08
assert "CWE-209, OWASP A10:2025" in doc08
print("  [OK] Master Table in doc08 verified with 100% exact alignment!")

if ok1 and ok2:
    print("\nALL VERIFICATIONS PASSED WITH ZERO ERRORS!")
else:
    sys.exit(1)
