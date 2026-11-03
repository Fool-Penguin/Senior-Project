"""
neural_oracle.py - Backward-compatibility re-export for NeuralOracle.
"""

from ..neuro.oracle import (
    OLLAMA_BASE_URL,
    REQUIRED_MODEL,
    NeuralOracle,
    extract_json_from_llm_response,
)

__all__ = [
    "NeuralOracle",
    "OLLAMA_BASE_URL",
    "REQUIRED_MODEL",
    "extract_json_from_llm_response",
]
