"""
Test Hybrid Sink-Aware + Vector RAG Retrieval vs Pure Vector RAG Retrieval on V3 (967 samples).
Let's see how much Recall@3 and Recall@5 improve when we combine:
1. ChromaDB dense vector similarity (ONNXMiniLM_L6_V2)
2. Symbolic Sink/API Token Matching against the 28 language-specific KB rules!
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
CHROMA_DIR = ROOT / "data" / "chromadb_kb"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_rows = [json.loads(line) for line in f if line.strip()]

with open(V3_PATH, "r", encoding="utf-8") as f:
    samples = [json.loads(line) for line in f if line.strip()]

# List all unique CWEs in KB
kb_cwes = sorted({r["cwe_id"] for r in kb_rows})
print(f"Unique CWEs in KB ({len(kb_cwes)}): {kb_cwes}")

# Notice: What happens when a sample is 3,000 chars long and the vulnerable sink is at char 2,200?
# Previously: query_text = "\n".join(meaningful_lines)[:2000] truncated anything after 2,000 chars!
# Also: MiniLM_L6_V2 has a max sequence length of 256 WordPiece tokens (~800 chars)!
# That means ChromaDB's ONNXMiniLM_L6_V2 silently truncates query_text after the first 256 tokens (~40 lines of code)!
print("\nCRITICAL DISCOVERY CHECK:")
long_samples = [s for s in samples if len(s["original_code"]) > 1000]
print(f"Samples > 1000 chars (exceeding MiniLM 256-token window): {len(long_samples)}/{len(samples)} ({len(long_samples)/len(samples)*100:.1f}%)")
