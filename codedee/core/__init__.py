"""CodeDEE Core Module Exports."""

from codedee.core.parser import CodeDEEParser, FunctionEntity, SupportedLanguage
from codedee.core.graph_builder import GraphBuilder, CodeGraphs
from codedee.core.metrics import MaintainabilityEngine, FileMetrics, FunctionMetrics
from codedee.core.taint_walker import SymbolicTaintWalker, TaintFinding

__all__ = [
    "CodeDEEParser",
    "FunctionEntity",
    "SupportedLanguage",
    "GraphBuilder",
    "CodeGraphs",
    "MaintainabilityEngine",
    "FileMetrics",
    "FunctionMetrics",
    "SymbolicTaintWalker",
    "TaintFinding",
]
