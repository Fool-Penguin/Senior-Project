# Handoff Report: ChromaDB Knowledge Base Seeding and RAG Retrieval for SQL Injection (CWE-89)

## 1. Observation

### 1.1 Knowledge Base Dataset (`mini_test_knowledges.json`)
- **File location**: `d:\4th-year\Senior-Project\codedee\codedee_server\data\mini_test_knowledges.json` (7,265 bytes, 139 lines).
- **Structure**: Exactly 8 JSON objects in a root array, each containing:
  - `id`: Unique identifier (e.g., `KNOW-CWE89-PY-SQLITE3`, `KNOW-CWE89-JS-PG`, `KNOW-CWE89-TS-TYPEORM`, `KNOW-CWE89-GENERAL-SANITY`).
  - `cwe_id`: Canonical CWE identifier `"CWE-89"`.
  - `language`: Target programming language (`"python"`, `"javascript"`, `"typescript"`, or `"all"`).
  - `framework`: Target DB driver / ORM (`"sqlite3"`, `"psycopg2"`, `"sqlalchemy"`, `"pg"`, `"mysql2"`, `"typeorm"`, `"prisma"`, `"general"`).
  - `category`: Defense strategy classification (`"parameterized_query"`, `"orm_parameterization"`, `"orm_tagged_template"`, `"input_validation"`).
  - `title`: Human-readable title summarizing the defense pattern.
  - `description`: Detailed explanation of the vulnerability mechanism and parameterization defense.
  - `vulnerable_pattern`: Verbatim code snippet showing vulnerable string concatenation or format.
  - `secure_pattern`: Verbatim code snippet showing parameterized, secure implementation.
  - `remediation_guide`: Step-by-step actionable remediation advice.
  - `metadata`: Sub-dictionary containing `placeholder_type` (`"?"`, `"%s"`, `"$1"`, `":param"`, `"tagged_template"`, `"allowlist_and_cast"`), `param_container` (`"tuple"`, `"array"`, `"dict"`, `"allowlist"`), and `sanitizer_type`.

### 1.2 Dependencies & ChromaDB Environment
- **`requirements.txt`**: Located at `d:\4th-year\Senior-Project\codedee\codedee_server\requirements.txt`. Line 22 specifies `chromadb>=0.4.24`.
- **Runtime Environment**:
  - Python version: `3.14.7` on `win32`.
  - Installed ChromaDB: `chromadb.__version__ == "1.5.9"`.
  - Embedding Function: Default is `chromadb.api.types.DefaultEmbeddingFunction`, which uses `ONNXMiniLM_L6_V2` (`all-MiniLM-L6-v2`).
  - Local Cache: Verified local presence at `C:\Users\Ongsa\.cache\chroma\onnx_models\all-MiniLM-L6-v2\onnx\model.onnx` and `tokenizer.json`. The model runs **100% offline with zero external network calls**.
- **Existing Persistent Storage**:
  - `d:\4th-year\Senior-Project\codedee\codedee_server\data\chroma_db` contains persistent SQLite DB `chroma.sqlite3` (2,662,400 bytes) and vector indices.

### 1.3 Existing Server Code Architecture vs `PROJECT.md` Specification
- **Existing Implementation**:
  - `app/knowledge/chroma_kb.py` (135 lines): Implements `ChromaKnowledgeBase` singleton using `chromadb.PersistentClient(path=str(self.persist_dir))` with fallback to `chromadb.Client()`. Uses collection name `"codedee_cwe89_knowledge"`.
  - `app/oracle/neural_oracle.py` (171 lines): Imports `from ..knowledge.chroma_kb import ChromaKnowledgeBase`, performs RAG retrieval (`n_results=2`), formats prompt with code slice + RAG context, and calls Ollama `qwen2.5-coder:7b` with deterministic fallback.
  - `app/slicer/program_slicer.py` (150 lines): Implements `ProgramSlicer` extracting enclosing function(s).
  - `app/verifier/multi_gate.py` (258 lines): Implements `MultiGateVerifier` for Gates 1, 2, 3, 4, 6.
  - `tests/test_neuro_verifier.py` (128 lines): Tests RAG seeding, slicing, multi-gate verifier, and neural oracle. All 7 tests currently pass.
- **`PROJECT.md` Structural Layout Specification**:
  - `PROJECT.md` (lines 166–176) specifies:
    ```
    codedee/codedee_server/app/neuro/
    ├── __init__.py
    ├── rag.py
    ├── slicer.py
    └── oracle.py
    codedee/codedee_server/scripts/seed_knowledge.py
    ```
  - Currently, `app/neuro/` does not exist (functionality is split into `app/knowledge/`, `app/slicer/`, and `app/oracle/`).
  - `scripts/seed_knowledge.py` does NOT exist yet (only `scripts/extract_dataset.py` exists).

### 1.4 Test Suite Status
- Running `pytest codedee/codedee_server/tests/`:
  - 110 passed in 18.65s.
  - `test_neuro_verifier.py` passes 100%.

---

## 2. Logic Chain

1. **Local Offline Determinism**:
   - `chromadb` 1.5.9 relies on `DefaultEmbeddingFunction` delegating to `onnxruntime` with `all-MiniLM-L6-v2`.
   - Inspection of `C:\Users\Ongsa\.cache\chroma\onnx_models\all-MiniLM-L6-v2` confirmed the model files (`model.onnx`, `tokenizer.json`, `vocab.txt`) are already resident on disk.
   - Empirical query execution across Python (`sqlite3`, `psycopg2`), JavaScript (`pg`, `mysql2`), and TypeScript (`typeorm`, `prisma`) executed in sub-second time without outbound HTTP requests.
   - Therefore, default ChromaDB embedding is completely safe, zero-dependency, and offline-compatible for CodeDEE.

2. **Client Setup (Persistent vs In-Memory)**:
   - For server operation, persistence to `data/chroma_db` prevents re-indexing on every API invocation.
   - In automated test suites or CI, file-based SQLite databases on Windows can encounter concurrent access or file locking issues.
   - Therefore, `ChromaKnowledgeBase` must support both `in_memory=True` (for testing) and persistent storage (for server runtime), with an automated fallback.

3. **Collection Naming & Metadata Filtering**:
   - `PROJECT.md` and dispatch require collection naming (e.g. `codedee_cwe_knowledge` or `codedee_cwe89_knowledge`).
   - Querying needs to support filtering by both `cwe_id` (e.g. `"CWE-89"`) and target `language` (`"python"`, `"javascript"`, `"typescript"`), while also matching entries designated as `"all"` (e.g. general sanity checks).
   - In ChromaDB, querying with multiple filters requires the `$and` and `$or` operators:
     `{"$and": [{"cwe_id": cwe_id}, {"$or": [{"language": language}, {"language": "all"}]}]}`.
   - We verified via direct Python execution that ChromaDB correctly evaluates this compound expression and isolates target language and universal defense records.

4. **Integration Gap Analysis**:
   - In `app/api/scan.py`, `NeuralOracle` is not invoked; instead, a hardcoded `NeuroAssessment` object is returned.
   - To realize true neuro-symbolic audit in Milestone 3, `POST /api/scan` must invoke `NeuralOracle.assess_finding()`, which executes `ProgramSlicer` and ChromaDB RAG.
   - To satisfy `PROJECT.md` directory layout while maintaining backward compatibility with existing tests, `app/neuro/` should be introduced with `rag.py`, `slicer.py`, and `oracle.py`, and `scripts/seed_knowledge.py` should be provided as a CLI entry point.

---

## 3. Caveats

1. **PowerShell Variable Interpolation in Ad-Hoc CLI**:
   - In PowerShell, strings containing `$and` or `$or` will be expanded as empty PowerShell variables if enclosed in double quotes. In Python application code, dictionary keys like `"$and"` and `"$or"` are standard strings and are unaffected.
2. **ChromaDB Thread-Safety**:
   - ChromaDB `PersistentClient` is thread-safe for reads, but concurrent write/seed operations during multi-worker FastAPI execution should be guarded via singleton instantiation during application lifespan startup.
3. **Ollama Reachability**:
   - `NeuralOracle` gracefully falls back to deterministic analysis when Ollama is offline or `qwen2.5-coder:7b` is unavailable. ChromaDB RAG retrieval operates completely independently of Ollama.

---

## 4. Conclusion

The ChromaDB vector store and RAG retrieval subsystem for CWE-89 is structurally sound, fast, and 100% offline. To complete Milestone 3 implementation cleanly:
1. Standardize `ChromaKnowledgeBase` in `app/neuro/rag.py` (and re-export to `app/knowledge/chroma_kb.py` for backward compatibility).
2. Configure collection name as `codedee_cwe_knowledge` (supporting configurable collection name and `in_memory` mode).
3. Update `query_knowledge` to support explicit `cwe_id: str = "CWE-89"` with compound `$and`/`$or` ChromaDB metadata filtering.
4. Implement `codedee/codedee_server/scripts/seed_knowledge.py` as a standalone CLI seeding utility.
5. Provide `app/neuro/__init__.py`, `app/neuro/slicer.py`, and `app/neuro/oracle.py` matching `PROJECT.md`.

---

## 5. Implementation Specifications & Code Proposals

### Specification 1: `codedee_server/app/neuro/rag.py`
```python
"""
rag.py - ChromaDB RAG Knowledge Base for CWE-89 Defense & Sanitization Patterns.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

logger = logging.getLogger(__name__)

KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mini_test_knowledges.json"
CHROMA_PERSIST_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "chroma_db"
DEFAULT_COLLECTION_NAME = "codedee_cwe_knowledge"


class ChromaKnowledgeBase:
    """
    Manages vector knowledge base for CWE-89 security patterns and sanitizers.
    Supports persistent disk storage or ephemeral in-memory storage for testing.
    """

    _instance: Optional["ChromaKnowledgeBase"] = None

    @classmethod
    def get_instance(
        cls,
        persist_dir: Optional[Path] = None,
        in_memory: bool = False,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ) -> "ChromaKnowledgeBase":
        if cls._instance is None:
            cls._instance = cls(
                persist_dir=persist_dir,
                in_memory=in_memory,
                collection_name=collection_name,
            )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for isolated unit test fixtures."""
        cls._instance = None

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        in_memory: bool = False,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ):
        self.in_memory = in_memory
        self.collection_name = collection_name
        self.persist_dir = persist_dir or CHROMA_PERSIST_DIR

        if self.in_memory:
            self.client = chromadb.Client()
        else:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            try:
                self.client = chromadb.PersistentClient(path=str(self.persist_dir))
            except Exception as e:
                logger.warning(f"Failed to initialize PersistentClient ({e}), falling back to in-memory Client.")
                self.client = chromadb.Client()

        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        self.seed_knowledge()

    def seed_knowledge(self, json_file: Optional[Path] = None, force_reload: bool = False) -> int:
        """Seed mini_test_knowledges.json entries into ChromaDB collection."""
        path = json_file or KNOWLEDGE_PATH
        if not path.exists():
            logger.warning(f"Knowledge file not found at {path}")
            return 0

        try:
            with open(path, "r", encoding="utf-8") as f:
                entries: List[Dict[str, Any]] = json.load(f)

            if not entries:
                return 0

            ids: List[str] = []
            documents: List[str] = []
            metadatas: List[Dict[str, Any]] = []

            for entry in entries:
                doc_id = entry.get("id") or f"KNOW-{len(ids)}"
                doc_text = (
                    f"Title: {entry.get('title')}\n"
                    f"Language: {entry.get('language')}\n"
                    f"Framework: {entry.get('framework')}\n"
                    f"Category: {entry.get('category')}\n"
                    f"Description: {entry.get('description')}\n"
                    f"Vulnerable Pattern: {entry.get('vulnerable_pattern')}\n"
                    f"Secure Pattern: {entry.get('secure_pattern')}\n"
                    f"Remediation: {entry.get('remediation_guide')}"
                )

                meta = {
                    "cwe_id": entry.get("cwe_id", "CWE-89"),
                    "language": entry.get("language", "all"),
                    "category": entry.get("category", "general"),
                    "framework": entry.get("framework", "general"),
                    "title": entry.get("title", ""),
                    "secure_pattern": entry.get("secure_pattern", ""),
                    "remediation_guide": entry.get("remediation_guide", ""),
                }

                ids.append(doc_id)
                documents.append(doc_text)
                metadatas.append(meta)

            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info(
                f"Successfully seeded {len(ids)} knowledge items into ChromaDB collection '{self.collection_name}'"
            )
            return len(ids)
        except Exception as e:
            logger.error(f"Error seeding ChromaDB: {e}")
            return 0

    def query_knowledge(
        self,
        query_text: str,
        language: Optional[str] = None,
        cwe_id: Optional[str] = "CWE-89",
        n_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Query ChromaDB for relevant CWE-89 defense and sanitizer patterns.
        Filters by cwe_id and target language (including universal 'all' entries).
        """
        try:
            filter_conditions: List[Dict[str, Any]] = []
            if cwe_id:
                filter_conditions.append({"cwe_id": cwe_id})

            if language and language.lower() in ("python", "javascript", "typescript"):
                filter_conditions.append({"$or": [{"language": language.lower()}, {"language": "all"}]})

            where_filter = None
            if len(filter_conditions) == 1:
                where_filter = filter_conditions[0]
            elif len(filter_conditions) > 1:
                where_filter = {"$and": filter_conditions}

            total_docs = max(self.collection.count(), 1)
            actual_k = min(n_results, total_docs)

            results = self.collection.query(
                query_texts=[query_text],
                n_results=actual_k,
                where=where_filter,
            )

            retrieved: List[Dict[str, Any]] = []
            if results and results.get("documents"):
                docs = results["documents"][0]
                metas = results.get("metadatas", [[]])[0]
                ids = results.get("ids", [[]])[0]
                distances = results.get("distances", [[]])[0] if results.get("distances") else [0.0] * len(docs)

                for doc_id, doc, meta, dist in zip(ids, docs, metas, distances):
                    retrieved.append({
                        "id": doc_id,
                        "document": doc,
                        "metadata": meta,
                        "distance": dist,
                        "title": meta.get("title", ""),
                        "secure_pattern": meta.get("secure_pattern", ""),
                        "remediation_guide": meta.get("remediation_guide", ""),
                    })
            return retrieved
        except Exception as e:
            logger.warning(f"Error querying ChromaDB: {e}")
            return []
```

### Specification 2: Standalone CLI Seeding Script `codedee_server/scripts/seed_knowledge.py`
```python
"""
seed_knowledge.py - Standalone CLI script to seed CWE-89 knowledge base into ChromaDB.
"""

import argparse
import sys
from pathlib import Path

# Add codedee_server to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.neuro.rag import ChromaKnowledgeBase, DEFAULT_COLLECTION_NAME, KNOWLEDGE_PATH


def main():
    parser = argparse.ArgumentParser(description="Seed CWE-89 security knowledge into ChromaDB.")
    parser.add_argument("--knowledge-file", type=Path, default=KNOWLEDGE_PATH, help="Path to mini_test_knowledges.json")
    parser.add_argument("--collection-name", type=str, default=DEFAULT_COLLECTION_NAME, help="ChromaDB collection name")
    parser.add_argument("--in-memory", action="store_true", help="Run with in-memory Chroma client")
    args = parser.parse_args()

    print(f"[*] Initializing ChromaKnowledgeBase (Collection: {args.collection_name})...")
    kb = ChromaKnowledgeBase(in_memory=args.in_memory, collection_name=args.collection_name)
    count = kb.seed_knowledge(json_file=args.knowledge_file)
    print(f"[+] Successfully seeded {count} defense patterns into ChromaDB.")


if __name__ == "__main__":
    main()
```

### Specification 3: Compatibility Alias `codedee_server/app/knowledge/chroma_kb.py`
```python
"""
chroma_kb.py - Backward-compatibility re-export for ChromaKnowledgeBase.
"""
from ..neuro.rag import ChromaKnowledgeBase, KNOWLEDGE_PATH, CHROMA_PERSIST_DIR

__all__ = ["ChromaKnowledgeBase", "KNOWLEDGE_PATH", "CHROMA_PERSIST_DIR"]
```

---

## 6. Verification Method

To independently verify this design:
1. **Pytest Suite Execution**:
   ```powershell
   pytest codedee/codedee_server/tests/test_neuro_verifier.py -v
   ```
   Ensures all existing tests pass and verifies vector retrieval for Python and JavaScript.
2. **Query Verification with CWE-89 & Language Filtering**:
   ```powershell
   python -c "import sys; sys.path.insert(0, 'codedee/codedee_server'); from app.knowledge.chroma_kb import ChromaKnowledgeBase; kb = ChromaKnowledgeBase.get_instance(); [print(lang, [r['id'] for r in kb.query_knowledge('query parameter', language=lang, n_results=2)]) for lang in ['python', 'javascript', 'typescript']]"
   ```
   Expected output:
   - `python` retrieves `KNOW-CWE89-PY-SQLITE3` / `KNOW-CWE89-PY-PSYCOPG2`.
   - `javascript` retrieves `KNOW-CWE89-JS-PG` / `KNOW-CWE89-JS-MYSQL2`.
   - `typescript` retrieves `KNOW-CWE89-TS-TYPEORM` / `KNOW-CWE89-TS-PRISMA`.
3. **Invalidation Conditions**:
   - If `all-MiniLM-L6-v2` ONNX model cannot be read or initialized without internet access.
   - If `$and` / `$or` metadata filtering causes ChromaDB query errors.
   - If `test_neuro_verifier.py` fails on any assertion.
