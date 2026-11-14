"""
Test improved RAG indexing & retrieval:
1. Strip leading line numbers ("123| ") and imports/comments.
2. Enrich ChromaDB KB documents with concrete sink API signatures & keywords.
3. Combine Multi-Window Vector Query (so code > 256 tokens is never truncated) + Sink Pattern Keyword Boost!
Let's measure Recall@1, Recall@3, Recall@5 on V3 (967 samples)!
"""
import json
import pathlib
import re
from collections import Counter
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
V3_PATH = ROOT / "datasets" / "combined" / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_rows = [json.loads(line) for line in f if line.strip()]

with open(V3_PATH, "r", encoding="utf-8") as f:
    samples = [json.loads(line) for line in f if line.strip()]

# Check how many samples in V3 have "123|" line number prefixes:
numbered_samples = sum(1 for s in samples if re.search(r"^\s*\d+\|", s["original_code"], re.MULTILINE))
print(f"Samples in V3 with '123|' line number prefixes: {numbered_samples}/{len(samples)}")
