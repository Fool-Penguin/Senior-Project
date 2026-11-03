import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import tree_sitter
import networkx as nx

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_ROOT))

from app.graphs.dfg import DFGBuilder
from app.taint.walker import SymbolicTaintWalker

class FixedDFGBuilder(DFGBuilder):
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

        # 1. Variable Identifier Read
        if node_type == "identifier":
            var_name = node_text
            use_id = f"{func_id}::use_{var_name}_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                use_id,
                node_id=use_id,
                var_name=var_name,
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="VAR_READ",
                expression_text=var_name,
                tainted=False,
                taint_source=None,
                ast_node=node,
            )
            # Def-Use edge
            if var_name in current_defs:
                self.graph.add_edge(current_defs[var_name], use_id, flow_type="DEF_USE", operation="read")
            return [use_id]

        # 2. Member / Attribute Access (e.g. req.query, request.args.get)
        if node_type in ("attribute", "member_expression"):
            attr_id = f"{func_id}::attr_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                attr_id,
                node_id=attr_id,
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
            # Look up base identifier
            base = node.child_by_field_name("object") or (node.children[0] if node.children else None)
            if base and base.type == "identifier":
                base_name = self.cst_manager.get_node_text(base, source_bytes)
                if base_name in current_defs:
                    self.graph.add_edge(current_defs[base_name], attr_id, flow_type="DEF_USE", operation="member_access")
            return [attr_id]

        # 3. String Concatenation: a + b
        if node_type in ("binary_operator", "binary_expression"):
            op_node = node.child_by_field_name("operator")
            op_text = self.cst_manager.get_node_text(op_node, source_bytes) if op_node else "+"
            left = node.child_by_field_name("left") or node.children[0]
            right = node.child_by_field_name("right") or node.children[-1]

            left_ids = self._process_expression(left, source_bytes, language, file_path, func_id, current_defs)
            right_ids = self._process_expression(right, source_bytes, language, file_path, func_id, current_defs)

            concat_id = f"{func_id}::binop_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                concat_id,
                node_id=concat_id,
                var_name="<binary_op>",
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="BINARY_OP",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=node,
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
            or (node_type == "string" and any(c.type == "interpolation" for c in node.children))
        )
        if is_fstring:
            fstr_id = f"{func_id}::fstring_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                fstr_id,
                node_id=fstr_id,
                var_name="<fstring>",
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="INTERPOLATION",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=node,
            )
            # Find all interpolation / format_expression children
            for child in node.children:
                if child.type == "interpolation":
                    for sub in child.children:
                        if sub.type not in ("{", "}", ":", "format_specifier"):
                            sub_ids = self._process_expression(sub, source_bytes, language, file_path, func_id, current_defs)
                            for sid in sub_ids:
                                self.graph.add_edge(sid, fstr_id, flow_type="FORMAT_INTERPOLATION", operation="f-string")
            return [fstr_id]

        # 5. Template Literal (JS / TS)
        if node_type == "template_string":
            tpl_id = f"{func_id}::template_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                tpl_id,
                node_id=tpl_id,
                var_name="<template_string>",
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="INTERPOLATION",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=node,
            )
            for child in node.children:
                if child.type == "template_substitution":
                    for sub in child.children:
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

            call_id = f"{func_id}::call_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                call_id,
                node_id=call_id,
                var_name=fn_text,
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="CALL_ARG",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=node,
            )

            # Process arguments
            if args_node:
                arg_idx = 0
                for arg_child in args_node.children:
                    if arg_child.type in ("(", ")", ",", "[", "]", "{", "}"):
                        continue
                    arg_ids = self._process_expression(arg_child, source_bytes, language, file_path, func_id, current_defs)
                    for aid in arg_ids:
                        self.graph.add_edge(aid, call_id, flow_type="ARG_TO_PARAM", operation=f"arg_{arg_idx}")
                    arg_idx += 1

            return [call_id]

        # ====================================================================
        # NEW / EXTENDED HANDLERS
        # ====================================================================

        # 7. Parenthesized Expressions (Grouping)
        # Transparently unwrap and forward inner expression value nodes
        if node_type == "parenthesized_expression":
            inner_ids: List[str] = []
            for child in node.children:
                if child.type not in ("(", ")", ";"):
                    inner_ids.extend(self._process_expression(child, source_bytes, language, file_path, func_id, current_defs))
            if inner_ids:
                return inner_ids

        # 8. Collections & Sequences: tuple, list, array, set, expression_list, sequence_expression
        if node_type in ("tuple", "list", "array", "set", "expression_list", "sequence_expression"):
            coll_id = f"{func_id}::coll_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                coll_id,
                node_id=coll_id,
                var_name=node_text,
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="COLLECTION",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=node,
            )
            for child in node.children:
                if child.type in ("(", ")", "[", "]", "{", "}", ",", ";"):
                    continue
                elem_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
                for eid in elem_ids:
                    self.graph.add_edge(eid, coll_id, flow_type="CONTAINER_ELEMENT", operation=node_type)
            return [coll_id]

        # 9. Dictionaries / Objects & Key-Value Pairs
        if node_type in ("dictionary", "object"):
            dict_id = f"{func_id}::dict_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                dict_id,
                node_id=dict_id,
                var_name=node_text,
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="COLLECTION",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=node,
            )
            for child in node.children:
                if child.type in ("{", "}", ",", ";"):
                    continue
                # child may be 'pair' or 'shorthand_property_identifier'
                val_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
                for vid in val_ids:
                    self.graph.add_edge(vid, dict_id, flow_type="CONTAINER_ELEMENT", operation="dict_entry")
            return [dict_id]

        if node_type == "pair":
            # For a dictionary/object pair 'key: value', propagate from the value expression (and key if dynamic)
            val_node = node.child_by_field_name("value") or (node.children[-1] if len(node.children) >= 3 else None)
            if val_node:
                return self._process_expression(val_node, source_bytes, language, file_path, func_id, current_defs)
            return []

        # 10. Syntactic wrappers / Type assertions (TS) / Await / Unary
        if node_type in ("await_expression", "as_expression", "type_assertion", "non_null_expression", "unary_operator", "unary_expression"):
            for child in node.children:
                if child.type not in ("await", "as", "!", "+", "-", "~", "not", "type_arguments", "predefined_type", "type_identifier"):
                    sub_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
                    if sub_ids:
                        return sub_ids

        # 11. Subscript / Indexing: req.args["user"], arr[i]
        if node_type in ("subscript", "subscript_expression"):
            val_node = node.child_by_field_name("value") or node.child_by_field_name("object")
            if val_node:
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
                val_ids = self._process_expression(val_node, source_bytes, language, file_path, func_id, current_defs)
                for vid in val_ids:
                    self.graph.add_edge(vid, sub_id, flow_type="DEF_USE", operation="subscript")
                return [sub_id]

        # 12. Fallback for literals / other expressions
        lit_id = f"{func_id}::lit_{node.start_point.row + 1}_{node.start_point.column}"
        self.graph.add_node(
            lit_id,
            node_id=lit_id,
            var_name=node_text,
            file_path=file_path,
            line_number=node.start_point.row + 1,
            col_offset=node.start_point.column,
            node_kind="STRING_LITERAL" if "string" in node_type else "EXPRESSION",
            expression_text=node_text,
            tainted=False,
            taint_source=None,
            ast_node=node,
        )
        return [lit_id]


print("FixedDFGBuilder defined successfully.")

# ============================================================================
# TEST HARNESS
# ============================================================================

import app.taint.walker
# Monkey-patch DFGBuilder in app.taint.walker to use FixedDFGBuilder
app.taint.walker.DFGBuilder = FixedDFGBuilder

walker = SymbolicTaintWalker()

def test_case(name, code, lang="python", expect_vuln=True):
    findings = walker.analyze_code(code, lang, f"{name}.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    print(f"Test '{name}': findings={len(findings)}, critical={len(critical)}")
    if expect_vuln:
        assert len(critical) >= 1, f"FAILED: Expected vulnerability in {name}, but got 0 critical findings!"
        print(f"  --> PASS (Detected {len(critical)} critical taint paths)")
        for idx, f in enumerate(critical):
            print(f"      Path {idx+1}: {len(f.taint_path)} steps")
            for step in f.taint_path:
                print(f"        Step {step['step_index']}: [{step['symbol']}] ({step['operation']}) -> {step['code_snippet']}")
    else:
        assert len(critical) == 0, f"FAILED: Expected SAFE in {name}, but got critical findings: {critical}"
        print(f"  --> PASS (Correctly identified as SAFE / sanitized)")

# Case 1: Tuple formatting % (username,)
test_case("tuple_single", """
from flask import request

def search_account():
    username = request.args.get("username")
    sql = "SELECT * FROM accounts WHERE name = '%s'" % (username,)
    cursor.execute(sql)
""")

# Case 2: Parenthesized formatting % (username)
test_case("paren_single", """
from flask import request

def search_account():
    username = request.args.get("username")
    sql = "SELECT * FROM accounts WHERE name = '%s'" % (username)
    cursor.execute(sql)
""")

# Case 3: List formatting % [username]
test_case("list_single", """
from flask import request

def search_account():
    username = request.args.get("username")
    sql = "SELECT * FROM accounts WHERE name = '%s'" % [username]
    cursor.execute(sql)
""")

# Case 4: Multiple tuple elements % (user, role)
test_case("tuple_multi", """
from flask import request

def search_account():
    user = request.args.get("user")
    role = request.args.get("role")
    sql = "SELECT * FROM accounts WHERE name = '%s' AND role = '%s'" % (user, role)
    cursor.execute(sql)
""")

# Case 5: Dictionary formatting % {"u": user}
test_case("dict_format", """
from flask import request

def search_account():
    user = request.args.get("user")
    sql = "SELECT * FROM accounts WHERE name = '%(u)s'" % {"u": user}
    cursor.execute(sql)
""")

# Case 6: Safe parameterized query cursor.execute(query, (user_id,))
test_case("safe_param", """
from flask import request

def safe_lookup():
    user_id = request.args.get("id")
    query = "SELECT * FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))
""", expect_vuln=False)

# Case 7: JavaScript array concatenation / formatting
test_case("js_array", """
function handle(req) {
    let u = req.query.u;
    let query = "SELECT * FROM t WHERE u = " + [u].join(",");
    db.query(query);
}
""", lang="javascript")

# Case 8: TypeScript type assertion
test_case("ts_type_assertion", """
function handle(req: any) {
    let u = (<string>req.query.u);
    let query = "SELECT * FROM t WHERE u = " + u;
    db.query(query);
}
""", lang="typescript")

# Case 9: Subscript index access
test_case("py_subscript", """
from flask import request

def search_account():
    username = request.args["username"]
    sql = "SELECT * FROM accounts WHERE name = '%s'" % (username,)
    cursor.execute(sql)
""")

print("\nALL PROTOTYPE TESTS PASSED SUCCESSFULLY!")



