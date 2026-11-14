"""
Analyze which CWEs in V3 are still missed at Top-3 by test_hybrid_rag.py and why!
"""
import json
import pathlib
import re
from collections import Counter
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from test_hybrid_rag import CWE_SINK_SIGNATURES, clean_code_for_rag_query

ROOT = pathlib.Path(__file__).parent.parent
V3_PATH = ROOT / "datasets" / "combined" / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl"
CHROMA_DIR = ROOT / "data" / "chromadb_kb"

with open(V3_PATH, "r", encoding="utf-8") as f:
    samples = [json.loads(line) for line in f if line.strip()]

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
embedding_fn = ONNXMiniLM_L6_V2()
collection = client.get_collection(name="codedee_knowledge_base", embedding_function=embedding_fn)

missed_by_cwe = Counter()
total_by_cwe = Counter()
sample_sink_by_cwe = {}

for s in samples:
    lang = s["language"].lower()
    code = s["original_code"]
    true_cwe = s["cwe_id"]
    total_by_cwe[true_cwe] += 1

    chunks = clean_code_for_rag_query(code)
    res = collection.query(
        query_texts=chunks,
        where={"language": lang},
        n_results=28,
        include=["metadatas", "distances"]
    )

    best_score_by_kb = {}
    meta_by_kb = {}
    for chunk_idx in range(len(chunks)):
        for m, d in zip(res["metadatas"][chunk_idx], res["distances"][chunk_idx]):
            kid = m["kb_id"]
            meta_by_kb[kid] = m
            if kid not in best_score_by_kb or d < best_score_by_kb[kid]:
                best_score_by_kb[kid] = d

    for kid, m in meta_by_kb.items():
        cwe = m["cwe_id"]
        patterns = CWE_SINK_SIGNATURES.get(cwe, [])
        match_count = sum(1 for pat in patterns if re.search(pat, code, re.IGNORECASE))
        if match_count > 0:
            best_score_by_kb[kid] -= min(0.35, 0.12 * match_count)

    ranked_kbs = sorted(best_score_by_kb.keys(), key=lambda k: best_score_by_kb[k])
    retrieved_cwes = []
    for kid in ranked_kbs:
        c = meta_by_kb[kid]["cwe_id"]
        if c not in retrieved_cwes:
            retrieved_cwes.append(c)

    if true_cwe not in retrieved_cwes[:3]:
        missed_by_cwe[true_cwe] += 1
        sample_sink_by_cwe.setdefault(true_cwe, []).append((lang, s.get("sink_pattern", ""), retrieved_cwes[:3]))

print("CWEs missed at Top-3 (sorted by missed count):")
for cwe, missed in missed_by_cwe.most_common():
    tot = total_by_cwe[cwe]
    print(f"  {cwe:10s}: Missed {missed:3d}/{tot:3d} (Recall@3 = {(tot-missed)/tot*100:5.1f}%)")
    for ex_lang, ex_sink, top3 in sample_sink_by_cwe[cwe][:2]:
        print(f"     -> [{ex_lang}] sink='{ex_sink[:70]}' | got Top-3: {top3}")
