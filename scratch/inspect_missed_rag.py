"""
Inspect a few samples from V3 where ChromaDB missed the true CWE at Top-3.
Why did ChromaDB miss them?
"""
import json
import pathlib
import re
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

ROOT = pathlib.Path(__file__).parent.parent
V3_PATH = ROOT / "datasets" / "combined" / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl"
CHROMA_DIR = ROOT / "data" / "chromadb_kb"

with open(V3_PATH, "r", encoding="utf-8") as f:
    samples = [json.loads(line) for line in f if line.strip()]

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
embedding_fn = ONNXMiniLM_L6_V2()
collection = client.get_collection(name="codedee_knowledge_base", embedding_function=embedding_fn)

# Print 5 missed samples
missed = 0
for s in samples:
    lang = s["language"].lower()
    code = s["original_code"]
    true_cwe = s["cwe_id"]
    lines = code.splitlines()
    meaningful_lines = [l for l in lines if not l.strip().startswith(('import ', 'from ', '#', '//', '/*'))]
    query_text = "\n".join(meaningful_lines)[:2000] if meaningful_lines else code[:2000]
    res = collection.query(query_texts=[query_text], where={"language": lang}, n_results=3, include=["metadatas", "distances"])
    top_cwes = [m["cwe_id"] for m in res["metadatas"][0]]
    if true_cwe not in top_cwes:
        print(f"Sample: {s['sample_id']} ({lang}) | True: {true_cwe} | Retrieved Top-3: {top_cwes}")
        print(f"  Sample sink_pattern field: {s.get('sink_pattern')}")
        print(f"  First 3 lines of query_text: {query_text.splitlines()[:3]}")
        missed += 1
        if missed >= 8:
            break
