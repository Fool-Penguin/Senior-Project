import sys
sys.path.insert(0, "scripts")
import run_full_scale_benchmark as b

col = b.get_chroma_collection()
samples, _ = b.load_dataset("v3")
s = samples[0]

print("ChromaDB collection count:", col.count())
print("Sample 0 ID:", s["sample_id"], "| Lang:", s["language"], "| True CWE:", s["cwe_id"])

rag_ctx = b.retrieve_rag_context(col, s["original_code"], s["language"], top_k=3)
print("\n--- Retrieved RAG Context (Top-3) ---")
print(rag_ctx[:600])

for mode in ["zero-shot", "one-shot", "few-shot", "cot"]:
    p = b.build_prompt(s, col, prompt_mode=mode, top_k=3)
    assert rag_ctx in p, f"RAG context missing in {mode}"
    print(f"Mode '{mode:9s}' -> total prompt chars: {len(p):5d}")

print("\nAll 4 prompt modes + Hybrid RAG verified successfully!")
