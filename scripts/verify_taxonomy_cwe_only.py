import csv
import re
import sys

print("--- Checking Taxonomy_table.csv ---")
with open('Taxonomy_table.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

assert len(rows) == 27, f"Expected 27 rows, got {len(rows)}"

errors = []
for i, r in enumerate(rows):
    ref = r['References']
    if 'OWASP' in ref:
        errors.append(f"Row {i+1} has OWASP in References: {ref}")
    if not re.match(r'^CWE-\d+$', ref):
        errors.append(f"Row {i+1} Reference '{ref}' does not match CWE-xxx pattern!")
    print(f"Row {i+1:2d}: {r['Name'][:35]:35s} -> {ref}")

# Specifically verify LLM entries
llm_rows = [r for r in rows if 'Prompt' in r['Name'] or 'Output Handling' in r['Name'] or 'Disclosure in Context' in r['Name']]
print("\n--- LLM Entries Verification ---")
for r in llm_rows:
    print(f"  {r['Name']:45s} -> {r['References']}")

# Check Uncovered table
print("\n--- Checking Uncovered_Taxonomy_table.csv ---")
with open('Uncovered_Taxonomy_table.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    unc_rows = list(reader)

for i, r in enumerate(unc_rows):
    ref = r['References']
    if 'OWASP' in ref:
        errors.append(f"Uncovered Row {i+1} has OWASP in References: {ref}")
    print(f"Uncovered Row {i+1:2d}: {r['Name'][:35]:35s} -> {ref}")

if errors:
    print("\nERRORS DETECTED:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
else:
    print("\nALL VERIFICATIONS PASSED WITH 0 ERRORS!")
