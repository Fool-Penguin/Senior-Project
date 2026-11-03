"""
chroma_kb.py - Backward-compatibility re-export for ChromaKnowledgeBase.
"""

from ..neuro.rag import (
    CHROMA_PERSIST_DIR,
    DEFAULT_COLLECTION_NAME,
    KNOWLEDGE_PATH,
    ChromaKnowledgeBase,
)

__all__ = [
    "ChromaKnowledgeBase",
    "KNOWLEDGE_PATH",
    "CHROMA_PERSIST_DIR",
    "DEFAULT_COLLECTION_NAME",
]
