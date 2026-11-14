"""
Check why VULN-XSS-001 (CWE-79) or other CWEs were missed at Top-3 by pure ChromaDB vector search,
and test a Hybrid Sink-Aware + Multi-Chunk ChromaDB RAG Retriever!
"""
import json
import pathlib
import re
from collections import Counter

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
V3_PATH = ROOT / "datasets" / "combined" / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_rows = [json.loads(line) for line in f if line.strip()]

py_kb = [r for r in kb_rows if r["language"] == "python"]
for r in py_kb:
    print(f"{r['catalogue_id']:16} | {r['cwe_id']:8} | {r['cwe_name'][:38]:38} | sinks: {r['sink_pattern'][:65]}")
