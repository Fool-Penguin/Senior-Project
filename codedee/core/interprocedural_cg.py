"""
CodeDEE - Semester 2: Inter-Procedural Call Graph & Taint Reachability Engine
Constructs project-wide directed call graphs across Python, JavaScript, and TypeScript,
and performs backward demand-driven reachability slicing for cross-file taint resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import networkx as nx
import tree_sitter

from codedee.core.parser import CodeDEEParser, FunctionEntity, SupportedLanguage
from codedee.core.symbol_resolver import ProjectSymbolResolver, ResolvedSymbol


@dataclass
class CallChainStep:
    """Represents a step in an inter-procedural call chain."""
    caller_symbol: str
    caller_file: str
    caller_function: str
    caller_params: list[str]
    call_line: int
    callee_symbol: str
    passed_args: list[str]


@dataclass
class InterproceduralTaintContext:
    """Consolidated cross-file context passed to Neural Oracle."""
    sink_symbol: str
    sink_file: str
    sink_function: str
    sink_callee: str
    source_symbol: str
    source_file: str
    source_function: str
    untrusted_params: list[str]
    call_depth: int
    call_chain: list[CallChainStep]
    caller_code_slice: str
    sink_code_slice: str


class InterproceduralCallGraph:
    """
    Project-Wide Inter-Procedural Call Graph Engine (NetworkX).
    Connects callers and callees across modules and performs backward slicing.
    """

    def __init__(self, symbol_resolver: ProjectSymbolResolver):
        self.resolver = symbol_resolver
        self.graph = nx.DiGraph()

    def build_project_graph(self):
        """Build the full project-wide call graph using resolved symbols."""
        # 1. Add all function nodes
        for sym_id, sym in self.resolver.symbols.items():
            self.graph.add_node(
                sym_id,
                file=sym.file_path,
                name=sym.function_name,
                params=sym.parameters,
                language=sym.language,
                start_line=sym.start_line,
                end_line=sym.end_line,
            )

        # 2. Add caller -> callee edges
        for rel_path, tree in self.resolver.file_trees.items():
            # Find all functions in this file
            file_symbols = [
                s for s in self.resolver.symbols.values() if s.file_path == rel_path
            ]
            
            for sym in file_symbols:
                caller_id = sym.symbol_id
                self._extract_calls_in_function(rel_path, caller_id, tree)

    def _extract_calls_in_function(
        self, rel_path: str, caller_id: str, tree: tree_sitter.Tree
    ):
        """Extract call expressions inside caller function and resolve edges."""
        sym = self.resolver.symbols[caller_id]
        start_line = sym.start_line
        end_line = sym.end_line

        def _traverse(node: tree_sitter.Node):
            # Check if node is inside this function's line range
            line = node.start_point[0] + 1
            if line < start_line or line > end_line:
                for c in node.children:
                    _traverse(c)
                return

            callee_name = None
            args_list = []

            # Python Call: func(arg1, arg2)
            if node.type == "call":
                fn_node = node.child_by_field_name("function")
                if fn_node and fn_node.text:
                    callee_name = fn_node.text.decode("utf-8")
                args_node = node.child_by_field_name("arguments")
                if args_node:
                    for arg in args_node.children:
                        if arg.text and arg.type not in ("(", ")", ","):
                            args_list.append(arg.text.decode("utf-8"))

            # JS/TS Call: func(arg1, arg2)
            elif node.type == "call_expression":
                fn_node = node.child_by_field_name("function")
                if fn_node and fn_node.text:
                    callee_name = fn_node.text.decode("utf-8")
                args_node = node.child_by_field_name("arguments")
                if args_node:
                    for arg in args_node.children:
                        if arg.text and arg.type not in ("(", ")", ","):
                            args_list.append(arg.text.decode("utf-8"))

            if callee_name:
                # Handle method access (e.g. self.do_query or db.execute)
                simple_callee = callee_name.split(".")[-1]
                callee_sym = self.resolver.resolve_callee(rel_path, simple_callee)
                if callee_sym:
                    self.graph.add_edge(
                        caller_id,
                        callee_sym.symbol_id,
                        relation="calls",
                        call_line=line,
                        passed_args=args_list,
                        raw_callee=callee_name,
                    )

            for c in node.children:
                _traverse(c)

        _traverse(tree.root_node)

    def get_backward_call_chains(
        self, sink_symbol_id: str, max_depth: int = 4
    ) -> list[list[str]]:
        """
        Traces all execution paths backwards from sink_symbol_id up to max_depth.
        Returns list of path node lists: [caller_k, ..., caller_1, sink_symbol_id]
        """
        if sink_symbol_id not in self.graph:
            return []

        paths = []

        def _dfs(current: str, current_path: list[str], depth: int):
            if depth >= max_depth:
                return
            predecessors = list(self.graph.predecessors(current))
            if not predecessors:
                if len(current_path) > 1:
                    paths.append(list(reversed(current_path)))
                return

            for pred in predecessors:
                if pred not in current_path:  # Avoid recursive cycles
                    current_path.append(pred)
                    _dfs(pred, current_path, depth + 1)
                    current_path.pop()

        _dfs(sink_symbol_id, [sink_symbol_id], 0)
        return paths

    def build_taint_context(
        self, sink_symbol_id: str, sink_callee: str, max_depth: int = 4
    ) -> Optional[InterproceduralTaintContext]:
        """
        Constructs an InterproceduralTaintContext identifying the upstream HTTP/user
        entrypoint that feeds into this sink_symbol_id.
        """
        chains = self.get_backward_call_chains(sink_symbol_id, max_depth=max_depth)
        if not chains:
            return None

        # Select the longest or entrypoint-originating chain
        primary_chain = max(chains, key=len)
        source_id = primary_chain[0]
        
        source_node = self.graph.nodes[source_id]
        sink_node = self.graph.nodes[sink_symbol_id]

        chain_steps: list[CallChainStep] = []
        for i in range(len(primary_chain) - 1):
            u = primary_chain[i]
            v = primary_chain[i + 1]
            edge_data = self.graph.edges.get((u, v), {})
            chain_steps.append(
                CallChainStep(
                    caller_symbol=u,
                    caller_file=self.graph.nodes[u].get("file", ""),
                    caller_function=self.graph.nodes[u].get("name", ""),
                    caller_params=self.graph.nodes[u].get("params", []),
                    call_line=edge_data.get("call_line", 0),
                    callee_symbol=v,
                    passed_args=edge_data.get("passed_args", []),
                )
            )

        return InterproceduralTaintContext(
            sink_symbol=sink_symbol_id,
            sink_file=sink_node.get("file", ""),
            sink_function=sink_node.get("name", ""),
            sink_callee=sink_callee,
            source_symbol=source_id,
            source_file=source_node.get("file", ""),
            source_function=source_node.get("name", ""),
            untrusted_params=source_node.get("params", []),
            call_depth=len(primary_chain) - 1,
            call_chain=chain_steps,
            caller_code_slice="",
            sink_code_slice="",
        )
