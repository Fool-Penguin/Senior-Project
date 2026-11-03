"""
program_slicer.py - Backward-compatibility re-export for ProgramSlicer.
"""

from ..neuro.slicer import FUNCTION_NODE_TYPES, ProgramSlicer

__all__ = ["ProgramSlicer", "FUNCTION_NODE_TYPES"]
