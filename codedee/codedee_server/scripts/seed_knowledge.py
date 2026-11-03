"""
seed_knowledge.py - Standalone CLI script to seed CWE-89 security knowledge into ChromaDB.
"""

import argparse
import sys
from pathlib import Path

# Add codedee_server to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.neuro.rag import (
    DEFAULT_COLLECTION_NAME,
    KNOWLEDGE_PATH,
    ChromaKnowledgeBase,
)


def seed_knowledge(
    knowledge_file: Path = KNOWLEDGE_PATH,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    in_memory: bool = False,
) -> int:
    """Seed CWE-89 security knowledge into ChromaDB."""
    kb = ChromaKnowledgeBase(in_memory=in_memory, collection_name=collection_name)
    return kb.seed_knowledge(json_file=knowledge_file)


seed_knowledge_base = seed_knowledge


def main():
    parser = argparse.ArgumentParser(description="Seed CWE-89 security knowledge into ChromaDB.")
    parser.add_argument(
        "--knowledge-file",
        type=Path,
        default=KNOWLEDGE_PATH,
        help="Path to mini_test_knowledges.json",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default=DEFAULT_COLLECTION_NAME,
        help="ChromaDB collection name",
    )
    parser.add_argument(
        "--in-memory",
        action="store_true",
        help="Run with in-memory Chroma client",
    )
    args = parser.parse_args()

    print(f"[*] Initializing ChromaKnowledgeBase (Collection: {args.collection_name})...")
    count = seed_knowledge(
        knowledge_file=args.knowledge_file,
        collection_name=args.collection_name,
        in_memory=args.in_memory,
    )
    print(f"[+] Successfully seeded {count} defense patterns into ChromaDB.")


if __name__ == "__main__":
    main()
