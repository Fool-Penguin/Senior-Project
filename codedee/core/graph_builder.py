"""
CodeDEE - Stage 2: Intermediate Graph Modeling (NetworkX)
Builds in-memory Call Graph, Control-Flow Graph (CFG), and Data-Flow Graph (DFG)
from Tree-sitter CSTs for Python, JavaScript, and TypeScript.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any
import networkx as nx
import tree_sitter

from codedee.core.parser import CodeDEEParser, FunctionEntity, SupportedLanguage


@dataclass
class CodeGraphs:
    """Bundle containing all 3 intermediate in-memory graphs for a code unit."""
    language: SupportedLanguage
    call_graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    cfg: nx.DiGraph = field(default_factory=nx.DiGraph)
    dfg: nx.DiGraph = field(default_factory=nx.DiGraph)
    functions: list[FunctionEntity] = field(default_factory=list)


class GraphBuilder:
    """Stage 2 Intermediate Graph Constructor."""

    @classmethod
    def build_all(cls, code: str, language: str) -> CodeGraphs:
        """Construct Call Graph, CFG, and DFG from source code."""
        tree, lang = CodeDEEParser.parse_string(code, language)
        functions = CodeDEEParser.extract_functions(code, lang)

        graphs = CodeGraphs(language=lang, functions=functions)
        
        # 1. Build Call Graph
        cls._build_call_graph(tree, functions, graphs.call_graph, lang)

        # 2. Build CFG for each function (or top-level module)
        cls._build_cfg(tree, functions, graphs.cfg, lang)

        # 3. Build DFG (Def-Use Taint chains)
        cls._build_dfg(tree, functions, graphs.dfg, lang)

        return graphs

    @classmethod
    def _build_call_graph(
        cls,
        tree: tree_sitter.Tree,
        functions: list[FunctionEntity],
        call_graph: nx.DiGraph,
        language: SupportedLanguage,
    ):
        """Build Call Graph identifying callers and callees."""
        fn_names = {f.name for f in functions}
        for f in functions:
            call_graph.add_node(f.name, kind="function", language=language, params=f.parameters)

        def _find_calls(node: tree_sitter.Node, current_fn: str):
            # Python call
            if language == "python" and node.type == "call":
                func_node = node.child_by_field_name("function")
                if func_node and func_node.text:
                    callee = func_node.text.decode("utf-8")
                    call_graph.add_node(callee, kind="callee")
                    call_graph.add_edge(current_fn, callee, relation="calls")

            # JS / TS call_expression
            elif language in ("javascript", "typescript") and node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node and func_node.text:
                    callee = func_node.text.decode("utf-8")
                    call_graph.add_node(callee, kind="callee")
                    call_graph.add_edge(current_fn, callee, relation="calls")

            for child in node.children:
                _find_calls(child, current_fn)

        for f in functions:
            _find_calls(f.node, f.name)

    @classmethod
    def _build_cfg(
        cls,
        tree: tree_sitter.Tree,
        functions: list[FunctionEntity],
        cfg: nx.DiGraph,
        language: SupportedLanguage,
    ):
        """Build Control-Flow Graph with branching edges (True/False/Next)."""
        for f in functions:
            entry_node = f"{f.name}:entry"
            exit_node = f"{f.name}:exit"
            cfg.add_node(entry_node, kind="entry", function=f.name)
            cfg.add_node(exit_node, kind="exit", function=f.name)

            branch_nodes = []
            stmt_nodes = []

            def _inspect_cf(node: tree_sitter.Node):
                # Branch conditions
                if node.type in ("if_statement", "for_statement", "while_statement", "try_statement"):
                    nid = f"{f.name}:{node.type}_{node.start_point[0]}_{node.start_point[1]}"
                    cfg.add_node(nid, kind="branch", type=node.type, line=node.start_point[0] + 1)
                    branch_nodes.append(nid)

                # Returns / exits
                elif node.type in ("return_statement", "raise_statement", "throw_statement"):
                    nid = f"{f.name}:{node.type}_{node.start_point[0]}_{node.start_point[1]}"
                    cfg.add_node(nid, kind="terminal", type=node.type, line=node.start_point[0] + 1)
                    cfg.add_edge(nid, exit_node, relation="exits")

                for child in node.children:
                    _inspect_cf(child)

            _inspect_cf(f.node)

            # Link sequential flow
            prev = entry_node
            for b in branch_nodes:
                cfg.add_edge(prev, b, relation="flow")
                prev = b
            if prev != entry_node:
                cfg.add_edge(prev, exit_node, relation="flow")
            else:
                cfg.add_edge(entry_node, exit_node, relation="flow")

    @classmethod
    def _build_dfg(
        cls,
        tree: tree_sitter.Tree,
        functions: list[FunctionEntity],
        dfg: nx.DiGraph,
        language: SupportedLanguage,
    ):
        """
        Build Data-Flow Graph (DFG) tracking Def-Use chains:
        Parameter Source -> Variable Assignment -> Sink Call Argument.
        """
        for f in functions:
            # 1. Add Parameters as Initial Taint Source Nodes
            for p in f.parameters:
                p_id = f"{f.name}:param:{p}"
                dfg.add_node(p_id, kind="param_source", var=p, function=f.name)

            # 2. Traverse assignments and expressions
            def _traverse_df(node: tree_sitter.Node):
                # Python assignments: assignment (left = right)
                if language == "python" and node.type == "assignment":
                    left = node.child_by_field_name("left")
                    right = node.child_by_field_name("right")
                    if left and right and left.text and right.text:
                        l_var = left.text.decode("utf-8")
                        r_expr = right.text.decode("utf-8")
                        var_id = f"{f.name}:var:{l_var}:{node.start_point[0]}"
                        dfg.add_node(var_id, kind="variable_def", var=l_var, line=node.start_point[0] + 1, function=f.name)

                        # Check if any parameter flows into right hand expression
                        for p in f.parameters:
                            if p in r_expr:
                                p_id = f"{f.name}:param:{p}"
                                dfg.add_edge(p_id, var_id, relation="flows_to")

                # JS / TS variable assignments
                elif language in ("javascript", "typescript") and node.type in ("variable_declarator", "assignment_expression"):
                    left = node.child_by_field_name("name") or node.child_by_field_name("left")
                    right = node.child_by_field_name("value") or node.child_by_field_name("right")
                    if left and right and left.text and right.text:
                        l_var = left.text.decode("utf-8")
                        r_expr = right.text.decode("utf-8")
                        var_id = f"{f.name}:var:{l_var}:{node.start_point[0]}"
                        dfg.add_node(var_id, kind="variable_def", var=l_var, line=node.start_point[0] + 1, function=f.name)

                        for p in f.parameters:
                            if p in r_expr:
                                p_id = f"{f.name}:param:{p}"
                                dfg.add_edge(p_id, var_id, relation="flows_to")

                # Calls / Potential Sinks: trace args
                is_call = (language == "python" and node.type == "call") or (
                    language in ("javascript", "typescript") and node.type == "call_expression"
                )
                if is_call:
                    func_n = node.child_by_field_name("function")
                    args_n = node.child_by_field_name("arguments")
                    if func_n and func_n.text and args_n and args_n.text:
                        func_name = func_n.text.decode("utf-8")
                        args_text = args_n.text.decode("utf-8")
                        sink_id = f"{f.name}:call:{func_name}:{node.start_point[0]}"
                        dfg.add_node(sink_id, kind="call_sink", callee=func_name, line=node.start_point[0] + 1)

                        # Edge from direct parameter
                        for p in f.parameters:
                            if p in args_text:
                                p_id = f"{f.name}:param:{p}"
                                dfg.add_edge(p_id, sink_id, relation="taint_sink_direct")

                        # Edge from defined variables
                        for n, d in list(dfg.nodes(data=True)):
                            if d.get("kind") == "variable_def" and d.get("function") == f.name:
                                vname = d.get("var")
                                if vname and vname in args_text:
                                    dfg.add_edge(n, sink_id, relation="taint_sink_propagated")

                for child in node.children:
                    _traverse_df(child)

            _traverse_df(f.node)
