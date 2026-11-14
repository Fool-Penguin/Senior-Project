"""
CodeDEE - ChromaDB Vector Store Builder for Knowledge Base
Loads datasets/combined/knowledge_base.jsonl (83 entries across Python, JS, TS)
Builds a persistent ChromaDB vector store under data/chromadb_kb/
"""

import json
import pathlib
import re
import shutil
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
CHROMA_DIR = ROOT / "data" / "chromadb_kb"
COLLECTION_NAME = "codedee_knowledge_base"


def strip_line_numbers(code_str: str) -> str:
    """Strip leading '123| ' line number prefixes so vector embeddings focus on code tokens."""
    if not code_str:
        return ""
    cleaned = [re.sub(r"^\s*\d+\|\s?", "", line) for line in code_str.splitlines()]
    return "\n".join(cleaned)


def build_knowledge_base_vector_store(force_rebuild=True):
    print("==================================================")
    print("Building CodeDEE ChromaDB Vector Store from KB")
    print(f"Source: {KB_PATH}")
    print(f"Target DB: {CHROMA_DIR}")
    print("==================================================")

    if force_rebuild and CHROMA_DIR.exists():
        print(f"Removing existing vector store at {CHROMA_DIR}...")
        shutil.rmtree(CHROMA_DIR)

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_fn = ONNXMiniLM_L6_V2()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"description": "CodeDEE 28 CWE / OWASP Knowledge Base with Source/Sink/Sanitizer patterns"}
    )

    ids = []
    documents = []
    metadatas = []

    with open(KB_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            d = json.loads(line)
            kb_id = d.get("kb_id", f"KB_{idx}")
            lang = d.get("language", "unknown").lower()
            cwe_id = d.get("cwe_id", "Unknown")
            cwe_name = d.get("cwe_name", "")
            cat_id = d.get("catalogue_id", "")
            owasp = d.get("owasp_category", "")
            sources = d.get("source_pattern", "")
            sinks = d.get("sink_pattern", "")
            sanitizers = d.get("sanitizer_pattern", "")
            has_example = bool(d.get("example_sample_id"))

            clean_orig = strip_line_numbers(d.get("example_original_code") or "")
            clean_fixed = strip_line_numbers(d.get("example_fixed_code") or "")

            # Construct rich semantic document optimized for ONNXMiniLM_L6_V2's 256-token window:
            # Place Dangerous Sink Patterns and Tainted Source Patterns first so they are never truncated!
            doc_parts = [
                f"Vulnerability: {cwe_id} - {cwe_name} ({lang})",
                f"Dangerous Sink Patterns: {sinks}",
                f"Tainted Source Patterns: {sources}",
                f"Valid Sanitizer Patterns: {sanitizers}",
                f"OWASP Category: {owasp} (Catalogue: {cat_id})",
            ]
            if has_example and clean_orig:
                # Add cleaned snippet of the flaw (up to 600 chars) to guide code-level similarity search
                orig_snippet = clean_orig[:600]
                doc_parts.append(f"Vulnerable Code Example:\n{orig_snippet}")

            doc_text = "\n".join(doc_parts)

            metadata = {
                "kb_id": kb_id,
                "catalogue_id": cat_id,
                "language": lang,
                "cwe_id": cwe_id,
                "cwe_name": cwe_name,
                "owasp_category": owasp,
                "has_example": has_example,
                "sources": sources[:400],
                "sinks": sinks[:400],
                "sanitizers": sanitizers[:400],
                "example_sample_id": d.get("example_sample_id") or "",
                "example_original_code": clean_orig[:1600],
                "example_fixed_code": clean_fixed[:1600]
            }

            ids.append(kb_id)
            documents.append(doc_text)
            metadatas.append(metadata)

    # Batch add to ChromaDB
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    print(f"Successfully ingested {len(ids)} knowledge base entries into ChromaDB collection '{COLLECTION_NAME}'!")
    
    # Test query
    test_res = collection.query(
        query_texts=["cursor.execute(sql_query)"],
        where={"language": "python"},
        n_results=2
    )
    print("Test Query Verification:")
    print("Matched IDs:", test_res["ids"])
    print("Matched CWEs:", [m.get("cwe_id") for m in test_res["metadatas"][0]])
    return client, collection


if __name__ == "__main__":
    build_knowledge_base_vector_store()

