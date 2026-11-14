"""
Audit ChromaDB RAG Recall@K and inspect how knowledge_base.jsonl is indexed and queried.
"""
import json
import pathlib
from collections import Counter
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
V3_PATH = ROOT / "datasets" / "combined" / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl"
CHROMA_DIR = ROOT / "data" / "chromadb_kb"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_rows = [json.loads(line) for line in f if line.strip()]

print(f"Total entries in knowledge_base.jsonl: {len(kb_rows)}")
lang_counts = Counter(r.get("language") for r in kb_rows)
print("KB entries by language:", dict(lang_counts))
ex_counts = Counter(bool(r.get("example_sample_id")) for r in kb_rows)
print("KB entries with example_sample_id:", dict(ex_counts))

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
embedding_fn = ONNXMiniLM_L6_V2()
collection = client.get_collection(name="codedee_knowledge_base", embedding_function=embedding_fn)
print("Total documents in ChromaDB collection:", collection.count())

with open(V3_PATH, "r", encoding="utf-8") as f:
    samples = [json.loads(line) for line in f if line.strip()]

# Check Recall@1, Recall@3, Recall@5, Recall@8 of current pure vector query
hits_at = {1: 0, 3: 0, 5: 0, 8: 0}
missed_cwes = Counter()

for s in samples:
    lang = s["language"].lower()
    code = s["original_code"]
    true_cwe = s["cwe_id"]

    lines = code.splitlines()
    meaningful_lines = [l for l in lines if not l.strip().startswith(('import ', 'from ', '#', '//', '/*'))]
    query_text = "\n".join(meaningful_lines)[:2000] if meaningful_lines else code[:2000]

    res = collection.query(
        query_texts=[query_text],
        where={"language": lang},
        n_results=8,
        include=["metadatas", "distances"]
    )
    retrieved_cwes = []
    for m in res["metadatas"][0]:
        c = m.get("cwe_id")
        if c not in retrieved_cwes:
            retrieved_cwes.append(c)

    for k in hits_at:
        if true_cwe in retrieved_cwes[:k]:
            hits_at[k] += 1
    if true_cwe not in retrieved_cwes[:3]:
        missed_cwes[true_cwe] += 1

n = len(samples)
print(f"\n--- Current Pure Vector RAG Retrieval Recall on V3 ({n} samples) ---")
for k, h in hits_at.items():
    print(f"Recall@{k}: {h}/{n} ({h/n*100:.2f}%)")
print("Top CWEs missed at Top-3:", missed_cwes.most_common(10))
