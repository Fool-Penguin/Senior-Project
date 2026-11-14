"""
Test why Recall@3 was 64.43% and test how Hybrid Sink-Aware + Vector RAG Retrieval improves Recall@1, Recall@3, Recall@5!
"""
import json
import pathlib
import re
from collections import Counter, defaultdict
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
V3_PATH = ROOT / "datasets" / "combined" / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl"
CHROMA_DIR = ROOT / "data" / "chromadb_kb"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_rows = [json.loads(line) for line in f if line.strip()]

with open(V3_PATH, "r", encoding="utf-8") as f:
    samples = [json.loads(line) for line in f if line.strip()]

# Check what happens when example_original_code has line numbers or boilerplate at the top
# Also check: in build_chromadb_kb.py, 16 KB entries had NO example_original_code!
# Wait: can we populate those 16 missing examples from V3, or why were they missing?
cwe_lang_in_v3 = Counter((s["language"].lower(), s["cwe_id"]) for s in samples)
for r in kb_rows:
    if not r.get("example_sample_id"):
        key = (r["language"].lower(), r["cwe_id"])
        print(f"Missing example in KB: {key} -> count in V3: {cwe_lang_in_v3[key]}")
