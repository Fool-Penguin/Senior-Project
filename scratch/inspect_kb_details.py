"""
Inspect why knowledge_base.jsonl has 16 entries without example_sample_id,
what fields exist in knowledge_base.jsonl, and why Recall@3 is 64.43%.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb = [json.loads(line) for line in f if line.strip()]

print("Sample KB entry keys:", list(kb[0].keys()))
print("Sample KB[0] metadata:", {k: str(v)[:120] for k, v in kb[0].items()})

missing_ex = [r for r in kb if not r.get("example_sample_id")]
print(f"\n16 KB entries missing example_sample_id:")
for r in missing_ex:
    print(f"  {r['kb_id']} | {r['language']} | {r['cwe_id']} ({r['cwe_name']}) | sink={r['sink_pattern'][:60]}")
