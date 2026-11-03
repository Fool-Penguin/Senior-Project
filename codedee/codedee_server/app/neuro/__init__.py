"""
app/neuro - Neuro-symbolic audit components: RAG knowledge base, CST program slicer, and neural oracle.
"""

from .rag import (
    CHROMA_PERSIST_DIR,
    DEFAULT_COLLECTION_NAME,
    KNOWLEDGE_PATH,
    ChromaKnowledgeBase,
)
from .slicer import FUNCTION_NODE_TYPES, ProgramSlicer
from .oracle import (
    OLLAMA_BASE_URL,
    REQUIRED_MODEL,
    NeuralOracle,
    extract_json_from_llm_response,
)

__all__ = [
    "ChromaKnowledgeBase",
    "DEFAULT_COLLECTION_NAME",
    "KNOWLEDGE_PATH",
    "CHROMA_PERSIST_DIR",
    "ProgramSlicer",
    "FUNCTION_NODE_TYPES",
    "NeuralOracle",
    "OLLAMA_BASE_URL",
    "REQUIRED_MODEL",
    "extract_json_from_llm_response",
]
