"""
cfg.py - Control-Flow Graph (CFG) builder using NetworkX.

Constructs intra-procedural directed control-flow graphs modeling branching statements
(if/elif/else, for, while, try/catch/finally, return) across Python, JavaScript, and TypeScript.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import networkx as nx
import tree_sitter

from ..parser.cst_manager import CSTParserManager, LanguageType


class CFGBuilder:
    """
    Constructs an intra-procedural Control-Flow Graph (CFG) for functions.
    """

    def __init__(self) -> None:
        self.cst_manager = CSTParserManager.get_instance()

    def build_for_function(
        self,
        func_node: tree_sitter.Node,
        source_bytes: bytes,
        language: str = "python",
        file_path: str = "",
        func_name: Optional[str] = None,
    ) -> nx.DiGraph:
        """
        Build CFG for a single function or method AST node.
        """
        graph = nx.DiGraph()
        norm_lang = self.cst_manager.normalize_language(language)

        if func_name is None:
            name_node = func_node.child_by_field_name("name")
            if name_node:
                func_name = self.cst_manager.get_node_text(name_node, source_bytes)
            else:
                func_name = f"anonymous_L{func_node.start_point.row + 1}"

        func_id = f"{file_path}::{func_name}" if file_path else func_name

        entry_id = f"{func_id}::ENTRY"
        exit_id = f"{func_id}::EXIT"

        graph.add_node(
            entry_id,
            func_id=func_id,
            block_type="ENTRY",
            start_line=func_node.start_point.row + 1,
            end_line=func_node.start_point.row + 1,
            statements=["ENTRY"],
            ast_node_type="entry",
        )
        graph.add_node(
            exit_id,
            func_id=func_id,
            block_type="EXIT",
            start_line=func_node.end_point.row + 1,
            end_line=func_node.end_point.row + 1,
            statements=["EXIT"],
            ast_node_type="exit",
        )

        # Locate body
        body_node = func_node.child_by_field_name("body")
        if not body_node:
            graph.add_edge(entry_id, exit_id, edge_type="FALLTHROUGH", condition=None)
            return graph

        # Collect statements in body
        stmts = [
            c for c in body_node.children
            if c.is_named and c.type not in (":", "{", "}", "comment")
        ]
        if not stmts:
            graph.add_edge(entry_id, exit_id, edge_type="FALLTHROUGH", condition=None)
            return graph

        node_counter = 0

        def create_stmt_node(
            ast_node: tree_sitter.Node,
            block_type: str = "BASIC_BLOCK",
            condition_expr: Optional[str] = None,
        ) -> str:
            nonlocal node_counter
            node_counter += 1
            node_id = f"{func_id}::stmt_{node_counter}"
            stmt_text = self.cst_manager.get_node_text(ast_node, source_bytes)
            graph.add_node(
                node_id,
                func_id=func_id,
                block_type=block_type,
                start_line=ast_node.start_point.row + 1,
                end_line=ast_node.end_point.row + 1,
                statements=[stmt_text],
                ast_node_type=ast_node.type,
                condition=condition_expr,
            )
            return node_id

        def process_sequence(
            statements: List[tree_sitter.Node],
            incoming_nodes: List[str],
        ) -> List[str]:
            """
            Process a linear sequence of statements, linking incoming control flow.
            Returns list of terminal outgoing nodes.
            """
            current_incoming = list(incoming_nodes)

            for stmt in statements:
                if not current_incoming:
                    # Dead code after unconditional return
                    break

                stmt_type = stmt.type

                # 1. IF STATEMENT
                if stmt_type == "if_statement":
                    cond_node = stmt.child_by_field_name("condition")
                    cond_text = self.cst_manager.get_node_text(cond_node, source_bytes) if cond_node else "condition"
                    header_id = create_stmt_node(stmt, block_type="BRANCH_HEADER", condition_expr=cond_text)

                    for inc in current_incoming:
                        graph.add_edge(inc, header_id, edge_type="FALLTHROUGH", condition=None)

                    # Then/consequence branch
                    conseq_node = stmt.child_by_field_name("consequence")
                    conseq_stmts = (
                        [c for c in conseq_node.children if c.is_named and c.type not in (":", "{", "}", "comment")]
                        if conseq_node else []
                    )

                    then_out = (
                        process_sequence(conseq_stmts, [header_id])
                        if conseq_stmts else [header_id]
                    )
                    # Label edge from header
                    for succ in graph.successors(header_id):
                        if graph[header_id][succ].get("edge_type") == "FALLTHROUGH":
                            graph[header_id][succ]["edge_type"] = "TRUE_BRANCH"
                            graph[header_id][succ]["condition"] = cond_text

                    # Else/alternative branch
                    alt_node = stmt.child_by_field_name("alternative")
                    else_out: List[str] = []
                    if alt_node:
                        # Could be else_clause or elif_clause
                        if alt_node.type in ("else_clause", "elif_clause"):
                            alt_body = alt_node.child_by_field_name("body") or alt_node
                            alt_stmts = [
                                c for c in alt_body.children
                                if c.is_named and c.type not in (":", "{", "}", "else", "elif", "comment")
                            ]
                            else_out = process_sequence(alt_stmts, [header_id])
                        else:
                            else_out = process_sequence([alt_node], [header_id])

                        # Set FALSE_BRANCH on edge from header to alternative target
                        for succ in graph.successors(header_id):
                            if graph[header_id][succ].get("edge_type") == "FALLTHROUGH":
                                graph[header_id][succ]["edge_type"] = "FALSE_BRANCH"
                                graph[header_id][succ]["condition"] = f"!({cond_text})"
                    else:
                        else_out = [header_id]

                    current_incoming = list(set(then_out + else_out))

                # 2. LOOPS (FOR / WHILE)
                elif stmt_type in ("for_statement", "while_statement", "for_in_statement", "for_of_statement", "do_statement"):
                    loop_header_id = create_stmt_node(stmt, block_type="LOOP_HEADER")
                    for inc in current_incoming:
                        graph.add_edge(inc, loop_header_id, edge_type="FALLTHROUGH", condition=None)

                    body_node = stmt.child_by_field_name("body")
                    loop_stmts = (
                        [c for c in body_node.children if c.is_named and c.type not in (":", "{", "}", "comment")]
                        if body_node else []
                    )

                    body_out = process_sequence(loop_stmts, [loop_header_id])
                    # Loop back edge
                    for b_out in body_out:
                        graph.add_edge(b_out, loop_header_id, edge_type="LOOP_BODY", condition="next_iteration")

                    # Loop exit edge
                    current_incoming = [loop_header_id]

                # 3. TRY / CATCH / EXCEPT / FINALLY
                elif stmt_type in ("try_statement",):
                    try_header_id = create_stmt_node(stmt, block_type="TRY_HEADER")
                    for inc in current_incoming:
                        graph.add_edge(inc, try_header_id, edge_type="FALLTHROUGH", condition=None)

                    body_node = stmt.child_by_field_name("body")
                    try_stmts = (
                        [c for c in body_node.children if c.is_named and c.type not in (":", "{", "}", "comment")]
                        if body_node else []
                    )
                    try_out = process_sequence(try_stmts, [try_header_id])

                    # Handlers (except_clause or catch_clause)
                    handler_nodes = [
                        c for c in stmt.children
                        if c.type in ("except_clause", "catch_clause")
                    ]
                    handler_outs: List[str] = []
                    for h in handler_nodes:
                        h_id = create_stmt_node(h, block_type="CATCH_BLOCK")
                        # Add exception edge from try block
                        graph.add_edge(try_header_id, h_id, edge_type="EXCEPTION_EDGE", condition="on_error")
                        h_body = h.child_by_field_name("body") or h
                        h_stmts = [
                            c for c in h_body.children
                            if c.is_named and c.type not in (":", "{", "}", "except", "catch", "comment")
                        ]
                        h_out = process_sequence(h_stmts, [h_id])
                        handler_outs.extend(h_out)

                    # Finally clause
                    finally_nodes = [c for c in stmt.children if c.type == "finally_clause"]
                    finally_outs: List[str] = []
                    if finally_nodes:
                        fin_id = create_stmt_node(finally_nodes[0], block_type="BASIC_BLOCK")
                        for t_out in try_out + handler_outs:
                            graph.add_edge(t_out, fin_id, edge_type="FALLTHROUGH", condition=None)
                        fin_body = finally_nodes[0].child_by_field_name("body") or finally_nodes[0]
                        fin_stmts = [
                            c for c in fin_body.children
                            if c.is_named and c.type not in (":", "{", "}", "finally", "comment")
                        ]
                        finally_outs = process_sequence(fin_stmts, [fin_id])
                        current_incoming = finally_outs
                    else:
                        current_incoming = list(set(try_out + handler_outs))

                # 4. RETURN STATEMENT
                elif stmt_type == "return_statement":
                    ret_id = create_stmt_node(stmt, block_type="BASIC_BLOCK")
                    for inc in current_incoming:
                        graph.add_edge(inc, ret_id, edge_type="FALLTHROUGH", condition=None)
                    graph.add_edge(ret_id, exit_id, edge_type="RETURN_EDGE", condition=None)
                    current_incoming = []  # Following statements are unreachable

                # 5. GENERAL STATEMENT
                else:
                    stmt_id = create_stmt_node(stmt, block_type="BASIC_BLOCK")
                    for inc in current_incoming:
                        graph.add_edge(inc, stmt_id, edge_type="FALLTHROUGH", condition=None)
                    current_incoming = [stmt_id]

            return current_incoming

        terminals = process_sequence(stmts, [entry_id])
        for term in terminals:
            if term != exit_id and not graph.has_edge(term, exit_id):
                graph.add_edge(term, exit_id, edge_type="FALLTHROUGH", condition=None)

        return graph

    def build_for_code(
        self,
        code: str,
        language: str = "python",
        file_path: str = "",
    ) -> Dict[str, nx.DiGraph]:
        """
        Build CFGs for all functions found in source code string.
        Returns a dictionary mapping function_name -> nx.DiGraph.
        """
        tree = self.cst_manager.parse(code, language)
        functions = self.cst_manager.get_functions(tree, language)
        source_bytes = code.encode("utf-8")
        cfgs: Dict[str, nx.DiGraph] = {}

        for fn in functions:
            name_node = fn.child_by_field_name("name")
            fn_name = (
                self.cst_manager.get_node_text(name_node, source_bytes)
                if name_node
                else f"fn_L{fn.start_point.row + 1}"
            )
            cfg = self.build_for_function(fn, source_bytes, language, file_path, fn_name)
            cfgs[fn_name] = cfg

        return cfgs
