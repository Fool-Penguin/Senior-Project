"""
Inspect the 16 KB entries without example_sample_id, and check how we can enrich
knowledge_base.jsonl + build_chromadb_kb.py + CWE_SINK_SIGNATURES to maximize RAG Recall@K.
"""
import json
import pathlib
import re
from collections import Counter

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
V3_PATH = ROOT / "datasets" / "combined" / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb = [json.loads(line) for line in f if line.strip()]

with open(V3_PATH, "r", encoding="utf-8") as f:
    v3 = [json.loads(line) for line in f if line.strip()]

# Group V3 by (language, cwe_id)
v3_by_lang_cwe = {}
for s in v3:
    key = (s["language"].lower(), s["cwe_id"])
    v3_by_lang_cwe.setdefault(key, []).append(s)

print("Checking 16 KB entries missing example_sample_id against V3:")
for r in kb:
    if not r.get("example_sample_id"):
        key = (r["language"].lower(), r["cwe_id"])
        matches = v3_by_lang_cwe.get(key, [])
        print(f"  {r['kb_id']} | {key} | V3 matches: {len(matches)} | sink_pattern: {r['sink_pattern'][:80]}")
