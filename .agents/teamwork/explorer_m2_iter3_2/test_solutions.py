import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

server_path = Path(r"d:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(server_path))

import networkx as nx
import tree_sitter
from app.graphs.dfg import DFGBuilder
from app.taint.walker import SymbolicTaintWalker

class FixedDFGBuilder(DFGBuilder):
    def _process_statement(
        self,
        stmt: tree_sitter.Node,
        source_bytes: bytes,
        language: str,
        file_path: str,
        func_id: str,
        current_defs: Dict[str, str],
    ) -> None:
        stmt_type = stmt.type

        # In Python and JS: expression_statement wraps assignments
        if stmt_type == "expression_statement" and stmt.children:
            for child in stmt.children:
                if child.type in ("assignment", "augmented_assignment", "assignment_expression"):
                    stmt = child
                    stmt_type = child.type
                    break

        # PYTHON ASSIGNMENT: var = expr OR container[0] = expr
        if stmt_type in ("assignment", "augmented_assignment"):
            left = stmt.child_by_field_name("left")
            right = stmt.child_by_field_name("right")

            rhs_nodes = self._process_expression(right, source_bytes, language, file_path, func_id, current_defs) if right else []

            # If left is an identifier (standard assignment)
            if left and left.type == "identifier":
                var_name = self.cst_manager.get_node_text(left, source_bytes)
                def_id = f"{func_id}::def_{var_name}_{left.start_point.row + 1}_{left.start_point.column}"
                expr_text = self.cst_manager.get_node_text(stmt, source_bytes)

                self.graph.add_node(
                    def_id,
                    node_id=def_id,
                    var_name=var_name,
                    file_path=file_path,
                    line_number=left.start_point.row + 1,
                    col_offset=left.start_point.column,
                    node_kind="ASSIGN_DEF",
                    expression_text=expr_text,
                    tainted=False,
                    taint_source=None,
                    ast_node=left,
                )

                for r_id in rhs_nodes:
                    self.graph.add_edge(r_id, def_id, flow_type="ASSIGNMENT", operation="=")

                if stmt_type == "augmented_assignment" and var_name in current_defs:
                    prev_def = current_defs[var_name]
                    self.graph.add_edge(prev_def, def_id, flow_type="STRING_CONCAT", operation="+=")

                current_defs[var_name] = def_id
                return

            # If left is a subscript: container[0] = user or data['key'] = user
            if left and left.type in ("subscript", "subscript_expression"):
                base_node = left.child_by_field_name("value") or left.child_by_field_name("object")
                if base_node and base_node.type == "identifier":
                    var_name = self.cst_manager.get_node_text(base_node, source_bytes)
                    def_id = f"{func_id}::def_{var_name}_{left.start_point.row + 1}_{left.start_point.column}"
                    expr_text = self.cst_manager.get_node_text(stmt, source_bytes)

                    self.graph.add_node(
                        def_id,
                        node_id=def_id,
                        var_name=var_name,
                        file_path=file_path,
                        line_number=left.start_point.row + 1,
                        col_offset=left.start_point.column,
                        node_kind="ASSIGN_DEF",
                        expression_text=expr_text,
                        tainted=False,
                        taint_source=None,
                        ast_node=left,
                    )

                    # Connect previous definition of container to this mutation definition
                    if var_name in current_defs:
                        self.graph.add_edge(current_defs[var_name], def_id, flow_type="CONTAINER_MUTATE", operation="update")

                    # Connect RHS value to definition of container
                    for r_id in rhs_nodes:
                        self.graph.add_edge(r_id, def_id, flow_type="CONTAINER_ELEMENT", operation="set_item")

                    current_defs[var_name] = def_id
                    return

        # Fall back to super for other statements (JS variable declarations, return, blocks, etc.)
        super()._process_statement(stmt, source_bytes, language, file_path, func_id, current_defs)

    def _process_expression(
        self,
        node: Optional[tree_sitter.Node],
        source_bytes: bytes,
        language: str,
        file_path: str,
        func_id: str,
        current_defs: Dict[str, str],
    ) -> List[str]:
        if node is None:
            return []

        node_type = node.type
        node_text = self.cst_manager.get_node_text(node, source_bytes)

        # Handle Python Keyword Arguments: name=expr
        if node_type == "keyword_argument":
            val_node = node.child_by_field_name("value")
            if val_node:
                return self._process_expression(val_node, source_bytes, language, file_path, func_id, current_defs)
            return []

        # Handle Splat/Spread expressions: *args, **kwargs, ...args
        if node_type in ("dictionary_splat", "list_splat", "spread_element"):
            for child in node.children:
                if child.is_named:
                    return self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
            return []

        # Handle Subscript / Indexing: container[0], data['key'], matrix[i][j]
        # Python: 'subscript' (child fields: 'value', 'subscript')
        # JS/TS: 'subscript_expression' (child fields: 'object', 'index')
        if node_type in ("subscript", "subscript_expression"):
            sub_id = f"{func_id}::subscript_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                sub_id,
                node_id=sub_id,
                var_name=node_text,
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="VAR_READ",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=node,
            )

            # Determine base container node
            base_node = node.child_by_field_name("value") or node.child_by_field_name("object")
            if base_node is None and node.children:
                base_node = node.children[0]

            if base_node:
                base_ids = self._process_expression(base_node, source_bytes, language, file_path, func_id, current_defs)
                for bid in base_ids:
                    self.graph.add_edge(bid, sub_id, flow_type="DEF_USE", operation="subscript")

            # Also process index/subscript if it carries dynamic expressions/taint
            index_node = node.child_by_field_name("subscript") or node.child_by_field_name("index")
            if index_node and index_node.type not in ("integer", "number", "string", "slice"):
                idx_ids = self._process_expression(index_node, source_bytes, language, file_path, func_id, current_defs)
                for iid in idx_ids:
                    self.graph.add_edge(iid, sub_id, flow_type="DEF_USE", operation="index")

            return [sub_id]

        return super()._process_expression(node, source_bytes, language, file_path, func_id, current_defs)

# Test LHS subscript assignment
import app.taint.walker as walker_module
old_builder = walker_module.DFGBuilder
walker_module.DFGBuilder = FixedDFGBuilder

walker = SymbolicTaintWalker()

code_lhs = """
from flask import request

def handler():
    user = request.args.get("user")
    container = []
    container[0] = user
    sql = "SELECT * FROM items WHERE owner = '%s'" % container[0]
    cursor.execute(sql)
"""
findings_lhs = walker.analyze_code(code_lhs, "python", "defect4_lhs.py")
print("LHS Subscript Assignment findings count:", len(findings_lhs))
for f in findings_lhs:
    print("  Finding:", f.cwe_id, f.severity, "sanitized=", f.sanitized, "steps:", len(f.taint_path))

walker_module.DFGBuilder = old_builder
