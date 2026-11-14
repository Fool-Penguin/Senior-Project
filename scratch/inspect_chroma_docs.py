"""
Inspect how build_chromadb_kb.py constructs doc_text and how retrieve_rag_context queries ChromaDB.
Let's test why Recall@3 was 64.4% and how improving doc_text + Sink-Aware Hybrid Retrieval boosts Recall@3!
"""
import json
import pathlib
import re
from collections import Counter

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_rows = [json.loads(line) for line in f if line.strip()]

for r in kb_rows[:5]:
    doc_parts = [
        f"Vulnerability: {r['cwe_id']} - {r['cwe_name']} (Catalogue: {r['catalogue_id']})",
        f"Programming Language: {r['language']}",
        f"OWASP Category: {r['owasp_category']}",
        f"Tainted Source Patterns: {r['source_pattern']}",
        f"Dangerous Sink Patterns: {r['sink_pattern']}",
        f"Valid Sanitizer Patterns: {r['sanitizer_pattern']}"
    ]
    if r.get("example_sample_id"):
        orig_snippet = r.get("example_original_code", "")[:400]
        doc_parts.append(f"Vulnerable Code Example:\n{orig_snippet}")
    doc_text = "\n".join(doc_parts)
    print(f"=== {r['kb_id']} (total len = {len(doc_text)} chars) ===")
    print(doc_text[:500])
    print("...\n")
