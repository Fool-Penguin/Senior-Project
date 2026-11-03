import sys
import networkx as nx
import tree_sitter
import pytest

sys.path.insert(0, 'codedee/codedee_server')
from app.parser.cst_manager import CSTParserManager
from app.graphs.dfg import DFGBuilder
from app.taint.walker import SymbolicTaintWalker

# Let's monkey-patch or subclass DFGBuilder to test our proposed fix!
def _extract_pattern_targets(self, node: tree_sitter.Node):
    """
    Recursively extract all target identifier CST nodes from an assignment LHS / pattern.
    Handles:
    - Direct identifiers (Python, JS, TS)
    - JS/TS: object_pattern, array_pattern, pair_pattern, shorthand_property_identifier_pattern,
             object_assignment_pattern, assignment_pattern, rest_pattern
    - Python: pattern_list, tuple_pattern, list_pattern, list_splat_pattern
    """
    if node is None:
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
        for child in node.children:
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
        for child in node.children:
            if child.is_named:
                targets.extend(self._extract_pattern_targets(child))
        return targets

    return []

original_process_statement = DFGBuilder._process_statement

def patched_process_statement(self, stmt, source_bytes, language, file_path, func_id, current_defs):
    stmt_type = stmt.type

    # Transparently unwrap expression_statement wrapping assignments
    if stmt_type == "expression_statement" and stmt.children:
        inner = stmt.children[0]
        if inner.type == "parenthesized_expression" and inner.children:
            for sub in inner.children:
                if sub.type in ("assignment", "augmented_assignment", "assignment_expression", "augmented_assignment_expression"):
                    stmt = sub
                    stmt_type = sub.type
                    break
        elif inner.type in ("assignment", "augmented_assignment", "assignment_expression", "augmented_assignment_expression"):
            stmt = inner
            stmt_type = inner.type

    # Unified ASSIGNMENT handling: Python (assignment, augmented_assignment) & JS/TS (assignment_expression, augmented_assignment_expression)
    if stmt_type in ("assignment", "augmented_assignment", "assignment_expression", "augmented_assignment_expression"):
        left = stmt.child_by_field_name("left")
        right = stmt.child_by_field_name("right")

        rhs_nodes = self._process_expression(right, source_bytes, language, file_path, func_id, current_defs) if right else []

        targets = self._extract_pattern_targets(left)
        if targets:
            expr_text = self.cst_manager.get_node_text(stmt, source_bytes)
            for target_node in targets:
                var_name = self.cst_manager.get_node_text(target_node, source_bytes)
                def_id = f"{func_id}::def_{var_name}_{target_node.start_point.row + 1}_{target_node.start_point.column}"

                self.graph.add_node(
                    def_id,
                    node_id=def_id,
                    var_name=var_name,
                    file_path=file_path,
                    line_number=target_node.start_point.row + 1,
                    col_offset=target_node.start_point.column,
                    node_kind="ASSIGN_DEF",
                    expression_text=expr_text,
                    tainted=False,
                    taint_source=None,
                    ast_node=target_node,
                )

                for r_id in rhs_nodes:
                    self.graph.add_edge(r_id, def_id, flow_type="ASSIGNMENT", operation="=")

                if stmt_type in ("augmented_assignment", "augmented_assignment_expression") and var_name in current_defs:
                    prev_def = current_defs[var_name]
                    self.graph.add_edge(prev_def, def_id, flow_type="STRING_CONCAT", operation="+=")

                current_defs[var_name] = def_id
            return

        # Subscript assignment: container[0] = user or data['key'] = user
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

                if var_name in current_defs:
                    self.graph.add_edge(current_defs[var_name], def_id, flow_type="CONTAINER_MUTATE", operation="update")

                for r_id in rhs_nodes:
                    self.graph.add_edge(r_id, def_id, flow_type="CONTAINER_ELEMENT", operation="set_item")

                current_defs[var_name] = def_id
                return
        return

    # JS/TS VARIABLE DECLARATION: const x = expr, let y = expr, const { a, b } = expr
    if stmt_type in ("variable_declaration", "lexical_declaration"):
        for decl in stmt.children:
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
                    def_id = f"{func_id}::def_{var_name}_{target_node.start_point.row + 1}_{target_node.start_point.column}"

                    self.graph.add_node(
                        def_id,
                        node_id=def_id,
                        var_name=var_name,
                        file_path=file_path,
                        line_number=target_node.start_point.row + 1,
                        col_offset=target_node.start_point.column,
                        node_kind="ASSIGN_DEF",
                        expression_text=expr_text,
                        tainted=False,
                        taint_source=None,
                        ast_node=target_node,
                    )

                    for r_id in rhs_nodes:
                        self.graph.add_edge(r_id, def_id, flow_type="ASSIGNMENT", operation="=")

                    current_defs[var_name] = def_id
        return

    # Fallback to original for return, block, etc.
    return original_process_statement(self, stmt, source_bytes, language, file_path, func_id, current_defs)

# Monkey-patch DFGBuilder
DFGBuilder._extract_pattern_targets = _extract_pattern_targets
DFGBuilder._process_statement = patched_process_statement

walker = SymbolicTaintWalker()

# Test 2A: JS Object destructuring
code_2a = """
function searchItems(req, res) {
    const { term } = req.query;
    const query = `SELECT * FROM items WHERE title = '${term}'`;
    db.query(query);
}
"""
findings_2a = walker.analyze_code(code_2a, language="javascript", file_path="destruct.js")
vulns_2a = [f for f in findings_2a if f.severity == "CRITICAL" and not f.sanitized]
print("Test 2A Vulns:", len(vulns_2a))
assert len(vulns_2a) >= 1

# Test 2B: TS aliased destructuring
code_2b = """
export function getUser(req: any) {
    const { id: userId } = req.params;
    const sql = "SELECT * FROM users WHERE id = '" + userId + "'";
    client.query(sql);
}
"""
findings_2b = walker.analyze_code(code_2b, language="typescript", file_path="alias_destruct.ts")
vulns_2b = [f for f in findings_2b if f.severity == "CRITICAL" and not f.sanitized]
print("Test 2B Vulns:", len(vulns_2b))
assert len(vulns_2b) >= 1

# Test 2C: JS array destructuring
code_2c = """
function filter(req) {
    const [term] = req.query.terms;
    const sql = `SELECT * FROM data WHERE tag = '${term}'`;
    pool.query(sql);
}
"""
findings_2c = walker.analyze_code(code_2c, language="javascript", file_path="arr_destruct.js")
vulns_2c = [f for f in findings_2c if f.severity == "CRITICAL" and not f.sanitized]
print("Test 2C Vulns:", len(vulns_2c))
assert len(vulns_2c) >= 1

# Test 2D: Python tuple unpacking
code_2d = """
def process():
    user, role = request.args.get('data').split(':')
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql)
"""
findings_2d = walker.analyze_code(code_2d, language="python", file_path="unpack.py")
vulns_2d = [f for f in findings_2d if f.severity == "CRITICAL" and not f.sanitized]
print("Test 2D Vulns:", len(vulns_2d))
assert len(vulns_2d) >= 1

print("\n>>> ALL 4 DEFECT 2 TESTS PASSED WITH 100% SUCCESS! <<<")
