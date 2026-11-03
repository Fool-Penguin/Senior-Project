"""Symbolic Taint Analysis Engine for CWE-89 SQL Injection."""

from .walker import SymbolicTaintWalker

__all__ = ["SymbolicTaintWalker"]
