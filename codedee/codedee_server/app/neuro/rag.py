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
DEFAULT_COLLECTION_NAME = "codedee_cwe89_knowledge"


class ChromaKnowledgeBase:
    """
    Manages vector knowledge base for CWE-89 security patterns and sanitizers.
    Supports persistent disk storage or ephemeral in-memory storage for testing.
    """

    COLLECTION_NAME = DEFAULT_COLLECTION_NAME
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
                logger.warning(
                    f"Failed to initialize PersistentClient ({e}), falling back to in-memory Client."
                )
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
                filter_conditions.append(
                    {"$or": [{"language": language.lower()}, {"language": "all"}]}
                )

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
                distances = (
                    results.get("distances", [[]])[0]
                    if results.get("distances")
                    else [0.0] * len(docs)
                )

                for doc_id, doc, meta, dist in zip(ids, docs, metas, distances):
                    meta_dict = meta if isinstance(meta, dict) else {}
                    retrieved.append({
                        "id": doc_id,
                        "document": doc,
                        "metadata": meta_dict,
                        "distance": dist,
                        "title": meta_dict.get("title", ""),
                        "secure_pattern": meta_dict.get("secure_pattern", ""),
                        "remediation_guide": meta_dict.get("remediation_guide", ""),
                    })
            return retrieved
        except Exception as e:
            logger.warning(f"Error querying ChromaDB: {e}")
            return []
