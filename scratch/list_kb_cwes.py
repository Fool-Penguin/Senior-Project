"""
Inspect all 84 entries in knowledge_base.jsonl and test Sink-Focused Querying + Hybrid Reranking.
"""
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_rows = [json.loads(line) for line in f if line.strip()]

for r in kb_rows[:28]:
    print(f"{r['catalogue_id']} | {r['cwe_id']} | {r['cwe_name'][:45]} | sinks: {r['sink_pattern'][:70]}")
