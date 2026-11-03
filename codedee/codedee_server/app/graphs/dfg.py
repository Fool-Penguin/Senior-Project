"""
dfg.py - Data-Flow Graph (DFG) builder using NetworkX.

Constructs directed data-flow graphs modeling Def-Use chains, string concatenations,
interpolations (f-strings, template literals), and inter-procedural argument-to-parameter
bindings across Python, JavaScript, and TypeScript.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, Union
import networkx as nx
import tree_sitter

from ..parser.cst_manager import CSTParserManager, LanguageType
from .call_graph import CallGraphBuilder


class DFGBuilder:
    """
    Constructs a Data-Flow Graph (DFG) modeling definitions, uses, and transformations.
    """

    def __init__(self, call_graph_builder: Optional[CallGraphBuilder] = None) -> None:
        self.cst_manager = CSTParserManager.get_instance()
        self.call_graph_builder = call_graph_builder
        self.graph: nx.DiGraph = nx.DiGraph()
        self.node_counter = 0

    def _next_node_id(self, prefix: str = "dfg") -> str:
        self.node_counter += 1
        return f"{prefix}_{self.node_counter}"

    def _pt(self, node: Optional[tree_sitter.Node], source_bytes: bytes) -> Tuple[int, int]:
        return self.cst_manager.get_node_point(node, source_bytes)

    def _end_pt(self, node: Optional[tree_sitter.Node], source_bytes: bytes) -> Tuple[int, int]:
        return self.cst_manager.get_node_end_point(node, source_bytes)

    def build_for_function(
        self,
        func_node: tree_sitter.Node,
        source_bytes: bytes,
        language: str = "python",
        file_path: str = "",
        func_name: Optional[str] = None,
    ) -> nx.DiGraph:
        """
        Build intra-procedural DFG for a single function AST node.
        """
        norm_lang = self.cst_manager.normalize_language(language)
        if func_name is None:
            name_node = func_node.child_by_field_name("name")
            fn_l, _ = self._pt(func_node, source_bytes)
            func_name = (
                self.cst_manager.get_node_text(name_node, source_bytes)
                if name_node
                else f"fn_L{fn_l}"
            )

        func_id = f"{file_path}::{func_name}" if file_path else func_name
        current_defs: Dict[str, str] = {}  # var_name -> last def node_id

        # 1. Process formal parameters
        params_node = func_node.child_by_field_name("parameters")
        if params_node:
            for child in params_node.named_children:
                p_name = None
                if child.type in ("identifier", "required_parameter", "optional_parameter"):
                    p_name_node = child.child_by_field_name("pattern") or child.child_by_field_name("name") or child
                    p_name = self.cst_manager.get_node_text(p_name_node, source_bytes)
                elif child.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
                    p_name_node = child.child_by_field_name("name") or (child.child(0) if child.child_count > 0 else None)
                    p_name = self.cst_manager.get_node_text(p_name_node, source_bytes)

                if p_name and p_name not in (",", "(", ")", ":", "self", "cls"):
                    c_line, c_col = self._pt(child, source_bytes)
                    param_id = f"{func_id}::param_{p_name}_{c_line}"
                    self.graph.add_node(
                        param_id,
                        node_id=param_id,
                        var_name=p_name,
                        file_path=file_path,
                        line_number=c_line,
                        col_offset=c_col,
                        node_kind="PARAM",
                        expression_text=p_name,
                        tainted=False,
                        taint_source=None,
                        ast_node=None,
                    )
                    current_defs[p_name] = param_id

        # 2. Traverse body
        body_node = func_node.child_by_field_name("body")
        if body_node:
            self._traverse_dfg_block(body_node, source_bytes, norm_lang, file_path, func_id, current_defs)

        return self.graph

    def _traverse_dfg_block(
        self,
        block_node: tree_sitter.Node,
        source_bytes: bytes,
        language: str,
        file_path: str,
        func_id: str,
        current_defs: Dict[str, str],
    ) -> None:
        """
        Traverse statements in a block, recording definitions and uses.
        """
        for stmt in block_node.named_children:
            if not stmt.is_named:
                continue

            # Don't recurse into nested functions here (they get their own DFG)
            if stmt.type in (
                "function_definition",
                "function_declaration",
                "class_definition",
                "class_declaration",
            ):
                continue

            self._process_statement(stmt, source_bytes, language, file_path, func_id, current_defs)

    def _extract_pattern_targets(self, node: Optional[tree_sitter.Node]) -> List[tree_sitter.Node]:
        """
        Recursively extract all target identifier CST nodes from an assignment LHS / pattern.
        Handles:
        - Direct identifiers (Python, JS, TS)
        - JS/TS pair pattern in object destructuring: pair_pattern (recurse ONLY into 'value')
        - Default values: assignment_pattern, object_assignment_pattern (recurse ONLY into 'left')
        - Rest patterns: rest_pattern, list_splat_pattern, list_splat
        - Composite patterns: object_pattern, array_pattern, pattern_list, tuple_pattern, list_pattern,
          parenthesized_expression, parenthesized_list_splat
        """
        if node is None or not node.is_named or node.type == "ERROR":
            return []

        node_type = node.type

        # 1. Base case: direct identifier
        if node_type in (
            "identifier",
            "shorthand_property_identifier",
            "shorthand_property_identifier_pattern",
        ):
            return [node]

        # 2. JS/TS pair pattern in object destructuring: { key: value }
        # Only the 'value' field contains the target variable/pattern!
        if node_type == "pair_pattern":
            val_node = node.child_by_field_name("value")
            return self._extract_pattern_targets(val_node) if val_node else []

        # 3. Default assignment patterns:
        # JS/TS assignment_pattern: [ a = 1 ] or { key: a = 1 } -> 'left' is target
        # JS/TS object_assignment_pattern: { a = 1 } -> 'left' is target
        if node_type in ("assignment_pattern", "object_assignment_pattern"):
            left_node = node.child_by_field_name("left")
            return self._extract_pattern_targets(left_node) if left_node else []

        # 4. Rest / splat patterns:
        # JS/TS rest_pattern: ...rest
        # Python list_splat_pattern / list_splat: *rest
        if node_type in ("rest_pattern", "list_splat_pattern", "list_splat"):
            targets = []
            for child in node.named_children:
                if child.is_named:
                    targets.extend(self._extract_pattern_targets(child))
            return targets

        # 5. Composite patterns / collections:
        # JS/TS: object_pattern, array_pattern
        # Python: pattern_list, tuple_pattern, list_pattern
        if node_type in (
            "object_pattern",
            "array_pattern",
            "pattern_list",
            "tuple_pattern",
            "list_pattern",
            "parenthesized_expression",
            "parenthesized_list_splat",
        ):
            targets = []
            for child in node.named_children:
                if child.is_named:
                    targets.extend(self._extract_pattern_targets(child))
            return targets

        return []

    def _process_statement(
        self,
        stmt: tree_sitter.Node,
        source_bytes: bytes,
        language: str,
        file_path: str,
        func_id: str,
        current_defs: Dict[str, str],
    ) -> None:
        """Process variable definitions and expressions inside a statement."""
        if not stmt or not stmt.is_named or stmt.type == "ERROR":
            return

        stmt_type = stmt.type

        # In Python and JS: expression_statement wraps assignments or parenthesized expressions
        if stmt_type == "expression_statement" and stmt.named_children:
            for child in stmt.named_children:
                if child.type == "parenthesized_expression" and child.named_children:
                    for sub in child.named_children:
                        if sub.type in (
                            "assignment",
                            "augmented_assignment",
                            "assignment_expression",
                            "augmented_assignment_expression",
                        ):
                            stmt = sub
                            stmt_type = sub.type
                            break
                    if stmt_type in (
                        "assignment",
                        "augmented_assignment",
                        "assignment_expression",
                        "augmented_assignment_expression",
                    ):
                        break
                elif child.type in (
                    "assignment",
                    "augmented_assignment",
                    "assignment_expression",
                    "augmented_assignment_expression",
                ):
                    stmt = child
                    stmt_type = child.type
                    break

        # UNIFIED ASSIGNMENT: Python (assignment, augmented_assignment) & JS/TS (assignment_expression, augmented_assignment_expression)
        if stmt_type in (
            "assignment",
            "augmented_assignment",
            "assignment_expression",
            "augmented_assignment_expression",
        ):
            left = stmt.child_by_field_name("left")
            right = stmt.child_by_field_name("right")

            rhs_nodes = self._process_expression(right, source_bytes, language, file_path, func_id, current_defs) if right else []

            targets = self._extract_pattern_targets(left)
            if targets:
                expr_text = self.cst_manager.get_node_text(stmt, source_bytes)
                for target_node in targets:
                    var_name = self.cst_manager.get_node_text(target_node, source_bytes)
                    tn_l, tn_c = self._pt(target_node, source_bytes)
                    def_id = f"{func_id}::def_{var_name}_{tn_l}_{tn_c}"

                    self.graph.add_node(
                        def_id,
                        node_id=def_id,
                        var_name=var_name,
                        file_path=file_path,
                        line_number=tn_l,
                        col_offset=tn_c,
                        node_kind="ASSIGN_DEF",
                        expression_text=expr_text,
                        tainted=False,
                        taint_source=None,
                        ast_node=None,
                    )

                    for r_id in rhs_nodes:
                        self.graph.add_edge(r_id, def_id, flow_type="ASSIGNMENT", operation="=")

                    if "augmented" in stmt_type and var_name in current_defs:
                        prev_def = current_defs[var_name]
                        self.graph.add_edge(prev_def, def_id, flow_type="STRING_CONCAT", operation="+=")

                    current_defs[var_name] = def_id
                return

            # Subscript assignment: container[0] = user or data['key'] = user or data['users'][0] = user
            if left and left.type in ("subscript", "subscript_expression"):
                curr_base = left.child(0) if left.child_count > 0 else None
                while curr_base and curr_base.type in ("subscript", "subscript_expression", "attribute", "member_expression"):
                    curr_base = curr_base.child(0) if curr_base.child_count > 0 else None

                if curr_base and curr_base.type == "identifier":
                    var_name = self.cst_manager.get_node_text(curr_base, source_bytes)
                    l_l, l_c = self._pt(left, source_bytes)
                    l_el, l_ec = self._end_pt(left, source_bytes)
                    def_id = f"{func_id}::def_{var_name}_{l_l}_{l_c}_{l_el}_{l_ec}"
                    expr_text = self.cst_manager.get_node_text(stmt, source_bytes)

                    self.graph.add_node(
                        def_id,
                        node_id=def_id,
                        var_name=var_name,
                        file_path=file_path,
                        line_number=l_l,
                        col_offset=l_c,
                        node_kind="ASSIGN_DEF",
                        expression_text=expr_text,
                        tainted=False,
                        taint_source=None,
                        ast_node=None,
                    )

                    if var_name in current_defs:
                        self.graph.add_edge(current_defs[var_name], def_id, flow_type="CONTAINER_MUTATE", operation="update")

                    for r_id in rhs_nodes:
                        self.graph.add_edge(r_id, def_id, flow_type="CONTAINER_ELEMENT", operation="set_item")

                    current_defs[var_name] = def_id
                    return
            return

        # JS/TS VARIABLE DECLARATION: const x = expr, let y = expr, const { term } = req.query
        if stmt_type in ("variable_declaration", "lexical_declaration"):
            for decl in stmt.named_children:
                if decl.type == "variable_declarator":
                    name_node = decl.child_by_field_name("name")
                    val_node = decl.child_by_field_name("value")

                    rhs_nodes = (
                        self._process_expression(val_node, source_bytes, language, file_path, func_id, current_defs)
                        if val_node
                        else []
                    )

                    targets = self._extract_pattern_targets(name_node)
                    expr_text = self.cst_manager.get_node_text(decl, source_bytes)
                    for target_node in targets:
                        var_name = self.cst_manager.get_node_text(target_node, source_bytes)
                        tn_l, tn_c = self._pt(target_node, source_bytes)
                        def_id = f"{func_id}::def_{var_name}_{tn_l}_{tn_c}"

                        self.graph.add_node(
                            def_id,
                            node_id=def_id,
                            var_name=var_name,
                            file_path=file_path,
                            line_number=tn_l,
                            col_offset=tn_c,
                            node_kind="ASSIGN_DEF",
                            expression_text=expr_text,
                            tainted=False,
                            taint_source=None,
                            ast_node=None,
                        )

                        for r_id in rhs_nodes:
                            self.graph.add_edge(r_id, def_id, flow_type="ASSIGNMENT", operation="=")

                        current_defs[var_name] = def_id
            return

        # JS/TS EXPRESSION STATEMENT: standalone expressions (e.g. calls, void invocations)
        if stmt_type == "expression_statement":
            for child in stmt.named_children:
                if child.type not in (";",):
                    self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
            return

        # RETURN STATEMENT
        if stmt_type == "return_statement":
            for child in stmt.named_children:
                if child.type not in ("return", ";"):
                    ret_nodes = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
                    st_l, st_c = self._pt(stmt, source_bytes)
                    ret_id = f"{func_id}::return_{st_l}"
                    self.graph.add_node(
                        ret_id,
                        node_id=ret_id,
                        var_name="<return>",
                        file_path=file_path,
                        line_number=st_l,
                        col_offset=st_c,
                        node_kind="RETURN_VAL",
                        expression_text=self.cst_manager.get_node_text(stmt, source_bytes),
                        tainted=False,
                        taint_source=None,
                        ast_node=None,
                    )
                    for r_node in ret_nodes:
                        self.graph.add_edge(r_node, ret_id, flow_type="RETURN_TRANSFER", operation="return")
            return

        # BLOCKS (if, for, while, try)
        body = stmt.child_by_field_name("body") or stmt.child_by_field_name("consequence")
        if body:
            self._traverse_dfg_block(body, source_bytes, language, file_path, func_id, current_defs)
        alt = stmt.child_by_field_name("alternative")
        if alt:
            alt_body = alt.child_by_field_name("body") or alt
            self._traverse_dfg_block(alt_body, source_bytes, language, file_path, func_id, current_defs)

    def _process_expression(
        self,
        node: Optional[tree_sitter.Node],
        source_bytes: bytes,
        language: str,
        file_path: str,
        func_id: str,
        current_defs: Dict[str, str],
    ) -> List[str]:
        """
        Recursively process expressions and create intermediate DFG nodes.
        Returns a list of node_ids representing the values produced by this expression.
        """
        if node is None or not node.is_named or node.type == "ERROR":
            return []

        node_type = node.type
        node_text = self.cst_manager.get_node_text(node, source_bytes)

        # 1. Variable Identifier Read
        if node_type == "identifier":
            var_name = node_text
            nl, nc = self._pt(node, source_bytes)
            use_id = f"{func_id}::use_{var_name}_{nl}_{nc}"
            self.graph.add_node(
                use_id,
                node_id=use_id,
                var_name=var_name,
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="VAR_READ",
                expression_text=var_name,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )
            # Def-Use edge
            if var_name in current_defs:
                self.graph.add_edge(current_defs[var_name], use_id, flow_type="DEF_USE", operation="read")
            return [use_id]

        # 2. Member / Attribute Access (e.g. req.query, request.args.get)
        if node_type in ("attribute", "member_expression"):
            nl, nc = self._pt(node, source_bytes)
            attr_id = f"{func_id}::attr_{nl}_{nc}"
            self.graph.add_node(
                attr_id,
                node_id=attr_id,
                var_name=node_text,
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="VAR_READ",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )
            # Look up base identifier from expression text safely without C pointer recursion
            base_name = node_text.split(".")[0].split("[")[0].strip()
            if base_name and base_name in current_defs:
                self.graph.add_edge(current_defs[base_name], attr_id, flow_type="DEF_USE", operation="member_access")
            elif node.child_count > 0:
                first_child = node.child(0)
                if first_child and first_child.type in ("call", "call_expression"):
                    curr_ids = self._process_expression(first_child, source_bytes, language, file_path, func_id, current_defs)
                    for cid in curr_ids:
                        self.graph.add_edge(cid, attr_id, flow_type="DEF_USE", operation="member_access")
            return [attr_id]

        # 3. String Concatenation: a + b
        if node_type in ("binary_operator", "binary_expression"):
            op_node = node.child_by_field_name("operator")
            op_text = self.cst_manager.get_node_text(op_node, source_bytes) if op_node else "+"
            left = node.child_by_field_name("left") or (node.child(0) if node.child_count > 0 else None)
            right = node.child_by_field_name("right") or (node.child(node.child_count - 1) if node.child_count > 0 else None)

            left_ids = self._process_expression(left, source_bytes, language, file_path, func_id, current_defs)
            right_ids = self._process_expression(right, source_bytes, language, file_path, func_id, current_defs)

            nl, nc = self._pt(node, source_bytes)
            nel, nec = self._end_pt(node, source_bytes)
            concat_id = f"{func_id}::binop_{nl}_{nc}_{nel}_{nec}"
            self.graph.add_node(
                concat_id,
                node_id=concat_id,
                var_name="<binary_op>",
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="BINARY_OP",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )

            flow_type = "STRING_CONCAT" if op_text in ("+", "%") else "OPERATION"
            for lid in left_ids:
                self.graph.add_edge(lid, concat_id, flow_type=flow_type, operation=op_text)
            for rid in right_ids:
                self.graph.add_edge(rid, concat_id, flow_type=flow_type, operation=op_text)

            return [concat_id]

        # 4. F-String / Interpolated String (Python)
        is_fstring = (
            node_type == "interpolated_string"
            or (node_type == "string" and any(c.type == "interpolation" for c in node.named_children))
        )
        if is_fstring:
            nl, nc = self._pt(node, source_bytes)
            fstr_id = f"{func_id}::fstring_{nl}_{nc}"
            self.graph.add_node(
                fstr_id,
                node_id=fstr_id,
                var_name="<fstring>",
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="INTERPOLATION",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )
            # Find all interpolation / format_expression children
            for child in node.named_children:
                if child.type == "interpolation":
                    for sub in child.named_children:
                        if sub.type not in ("{", "}", ":", "format_specifier"):
                            sub_ids = self._process_expression(sub, source_bytes, language, file_path, func_id, current_defs)
                            for sid in sub_ids:
                                self.graph.add_edge(sid, fstr_id, flow_type="FORMAT_INTERPOLATION", operation="f-string")
            return [fstr_id]

        # 5. Template Literal (JS / TS)
        if node_type == "template_string":
            nl, nc = self._pt(node, source_bytes)
            tpl_id = f"{func_id}::template_{nl}_{nc}"
            self.graph.add_node(
                tpl_id,
                node_id=tpl_id,
                var_name="<template_string>",
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="INTERPOLATION",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )
            for child in node.named_children:
                if child.type == "template_substitution":
                    for sub in child.named_children:
                        if sub.type not in ("${", "}"):
                            sub_ids = self._process_expression(sub, source_bytes, language, file_path, func_id, current_defs)
                            for sid in sub_ids:
                                self.graph.add_edge(sid, tpl_id, flow_type="FORMAT_INTERPOLATION", operation="template_literal")
            return [tpl_id]

        # 6. Function Calls: fn(arg1, arg2)
        if node_type in ("call", "call_expression"):
            fn_node = node.child_by_field_name("function")
            fn_text = self.cst_manager.get_node_text(fn_node, source_bytes) if fn_node else "call"
            args_node = node.child_by_field_name("arguments")

            nl, nc = self._pt(node, source_bytes)
            nel, nec = self._end_pt(node, source_bytes)
            call_id = f"{func_id}::call_{nl}_{nc}_{nel}_{nec}"
            self.graph.add_node(
                call_id,
                node_id=call_id,
                var_name=fn_text,
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="CALL_ARG",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )

            # Connect receiver object for method invocations (e.g. raw_user.replace(...), user.strip())
            if fn_node and fn_node.type in ("attribute", "member_expression"):
                recv_node = fn_node.child_by_field_name("object")
                if recv_node:
                    recv_ids = self._process_expression(recv_node, source_bytes, language, file_path, func_id, current_defs)
                    for rid in recv_ids:
                        self.graph.add_edge(rid, call_id, flow_type="ARG_TO_PARAM", operation="receiver")

            # Process arguments
            if args_node:
                arg_idx = 0
                for arg_child in args_node.named_children:
                    if arg_child.type in ("(", ")", ",", "[", "]", "{", "}"):
                        continue
                    kw_name = None
                    if arg_child.type == "keyword_argument":
                        k_name_node = arg_child.child_by_field_name("name")
                        if k_name_node:
                            kw_name = self.cst_manager.get_node_text(k_name_node, source_bytes)

                    arg_ids = self._process_expression(arg_child, source_bytes, language, file_path, func_id, current_defs)
                    op_str = f"kwarg_{kw_name}" if kw_name else f"arg_{arg_idx}"
                    for aid in arg_ids:
                        self.graph.add_edge(aid, call_id, flow_type="ARG_TO_PARAM", operation=op_str)
                    arg_idx += 1

            return [call_id]

        # 7. Parenthesized Expressions (Grouping)
        # Transparently unwrap and forward inner expression value nodes
        if node_type == "parenthesized_expression":
            inner_ids: List[str] = []
            for child in node.named_children:
                if child.type not in ("(", ")", ";"):
                    inner_ids.extend(self._process_expression(child, source_bytes, language, file_path, func_id, current_defs))
            if inner_ids:
                return inner_ids

        # 8. Collections & Sequences: tuple, list, array, set, expression_list, sequence_expression
        if node_type in ("tuple", "list", "array", "set", "expression_list", "sequence_expression"):
            nl, nc = self._pt(node, source_bytes)
            coll_id = f"{func_id}::coll_{nl}_{nc}"
            self.graph.add_node(
                coll_id,
                node_id=coll_id,
                var_name=node_text,
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="COLLECTION",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )
            for child in node.named_children:
                if child.type in ("(", ")", "[", "]", "{", "}", ",", ";"):
                    continue
                elem_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
                for eid in elem_ids:
                    self.graph.add_edge(eid, coll_id, flow_type="CONTAINER_ELEMENT", operation=node_type)
            return [coll_id]

        # 8b. Subscript / Indexing Access: container[0], data['key'], matrix[i][j]
        # Python: 'subscript' (child fields: 'value', 'subscript')
        # JS/TS: 'subscript_expression' (child fields: 'object', 'index')
        if node_type in ("subscript", "subscript_expression"):
            nl, nc = self._pt(node, source_bytes)
            nel, nec = self._end_pt(node, source_bytes)
            sub_id = f"{func_id}::subscript_{nl}_{nc}_{nel}_{nec}"
            self.graph.add_node(
                sub_id,
                node_id=sub_id,
                var_name=node_text,
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="VAR_READ",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )

            # Determine base container node safely
            base_name = node_text.split("[")[0].strip()
            root_name = base_name.split(".")[0].strip()
            if base_name and base_name in current_defs:
                self.graph.add_edge(current_defs[base_name], sub_id, flow_type="DEF_USE", operation="subscript")
            elif root_name and root_name in current_defs:
                self.graph.add_edge(current_defs[root_name], sub_id, flow_type="DEF_USE", operation="subscript")
            elif node.child_count > 0:
                base_node = node.child(0)
                if base_node and base_node.type in ("subscript", "subscript_expression", "call", "call_expression"):
                    base_ids = self._process_expression(base_node, source_bytes, language, file_path, func_id, current_defs)
                    for bid in base_ids:
                        self.graph.add_edge(bid, sub_id, flow_type="DEF_USE", operation="subscript")

            # Process dynamic index expression if tainted/non-literal
            index_node = node.child(2) if node.child_count >= 3 else None
            if index_node and index_node.type not in ("integer", "number", "string", "slice"):
                idx_ids = self._process_expression(index_node, source_bytes, language, file_path, func_id, current_defs)
                for iid in idx_ids:
                    self.graph.add_edge(iid, sub_id, flow_type="DEF_USE", operation="index")

            return [sub_id]

        # 9. Dictionaries / Objects & Key-Value Pairs
        if node_type in ("dictionary", "object"):
            nl, nc = self._pt(node, source_bytes)
            dict_id = f"{func_id}::dict_{nl}_{nc}"
            self.graph.add_node(
                dict_id,
                node_id=dict_id,
                var_name=node_text,
                file_path=file_path,
                line_number=nl,
                col_offset=nc,
                node_kind="COLLECTION",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=None,
            )
            for child in node.named_children:
                if child.type in ("{", "}", ",", ";"):
                    continue
                val_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
                for vid in val_ids:
                    self.graph.add_edge(vid, dict_id, flow_type="CONTAINER_ELEMENT", operation="dict_entry")
            return [dict_id]

        if node_type == "pair":
            val_node = node.child_by_field_name("value") or (node.child(node.child_count - 1) if node.child_count >= 3 else None)
            if val_node:
                return self._process_expression(val_node, source_bytes, language, file_path, func_id, current_defs)
            return []

        # 9b. Python Keyword Arguments: name=expr
        if node_type == "keyword_argument":
            val_node = node.child_by_field_name("value")
            if val_node:
                return self._process_expression(val_node, source_bytes, language, file_path, func_id, current_defs)
            return []

        # 9c. Splats & Spreads: *args, **kwargs (Python), ...args (JS/TS)
        if node_type in ("dictionary_splat", "list_splat", "spread_element"):
            for child in node.named_children:
                if child.is_named:
                    return self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
            return []

        # 10. Syntactic wrappers / Type assertions (TS) / Await / Unary
        if node_type in ("await", "await_expression", "as_expression", "type_assertion", "non_null_expression", "unary_operator", "unary_expression"):
            for child in node.named_children:
                if child.type not in ("await", "as", "!", "+", "-", "~", "not", "type_arguments", "predefined_type", "type_identifier", ";"):
                    sub_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
                    if sub_ids:
                        return sub_ids

        # 11. Fallback for literals / other expressions
        nl, nc = self._pt(node, source_bytes)
        lit_id = f"{func_id}::lit_{nl}_{nc}"
        self.graph.add_node(
            lit_id,
            node_id=lit_id,
            var_name=node_text,
            file_path=file_path,
            line_number=nl,
            col_offset=nc,
            node_kind="STRING_LITERAL" if "string" in node_type else "EXPRESSION",
            expression_text=node_text,
            tainted=False,
            taint_source=None,
            ast_node=None,
        )
        return [lit_id]

    def build_for_code(
        self,
        code: str,
        language: str = "python",
        file_path: str = "",
    ) -> nx.DiGraph:
        """
        Build DFG for an entire file by parsing and analyzing top-level statements and all functions.
        """
        tree = self.cst_manager.parse(code, language)
        self.tree = tree
        source_bytes = code.encode("utf-8")
        self.source_bytes = source_bytes
        functions = self.cst_manager.get_functions(tree, language)

        for fn in functions:
            name_node = fn.child_by_field_name("name")
            fn_l, _ = self._pt(fn, source_bytes)
            fn_name = (
                self.cst_manager.get_node_text(name_node, source_bytes)
                if name_node
                else f"fn_L{fn_l}"
            )
            self.build_for_function(fn, source_bytes, language, file_path, fn_name)

        # Also process top-level script statements if any
        current_defs: Dict[str, str] = {}
        for child in tree.root_node.named_children:
            if child.is_named and child.type not in ("function_definition", "function_declaration", "class_definition", "ERROR"):
                self._process_statement(child, source_bytes, language, file_path, f"{file_path}::<module>", current_defs)

        return self.graph

    def link_inter_procedural_calls(self, call_graph: nx.DiGraph) -> None:
        """
        Using the Call Graph, add cross-function and cross-file ARG_TO_PARAM and RETURN_TRANSFER edges in the DFG.
        """
        for caller_id, callee_id, edge_data in call_graph.edges(data=True):
            if callee_id.startswith("external::"):
                continue

            callee_data = call_graph.nodes.get(callee_id, {})
            callee_params = callee_data.get("parameters", [])
            callee_file = callee_data.get("file_path", "")
            callee_name = callee_data.get("name", "")

            call_line = edge_data.get("call_line")
            # Find caller's CALL_ARG nodes for this call site
            matching_call_nodes = [
                n for n, d in self.graph.nodes(data=True)
                if d.get("line_number") == call_line and d.get("node_kind") == "CALL_ARG"
            ]

            for call_node in matching_call_nodes:
                # Find arguments feeding into this call node
                in_edges = self.graph.in_edges(call_node, data=True)
                for src, _, ed in in_edges:
                    op = ed.get("operation", "")
                    param_name = None
                    if op.startswith("kwarg_"):
                        param_name = op[len("kwarg_"):]
                    elif op.startswith("arg_"):
                        try:
                            arg_idx = int(op.split("_")[1])
                            if arg_idx < len(callee_params):
                                param_name = callee_params[arg_idx]
                        except ValueError:
                            continue

                    if param_name:
                        # Find target parameter node in callee DFG
                        target_param_nodes = [
                            n for n, d in self.graph.nodes(data=True)
                            if d.get("var_name") == param_name
                            and d.get("node_kind") == "PARAM"
                            and (d.get("file_path") == callee_file or callee_name in n)
                        ]
                        for tp in target_param_nodes:
                            self.graph.add_edge(
                                src,
                                tp,
                                flow_type="ARG_TO_PARAM",
                                operation=f"bind({param_name})",
                            )
