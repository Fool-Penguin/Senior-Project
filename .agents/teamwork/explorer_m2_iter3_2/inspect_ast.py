import sys
from pathlib import Path

server_path = Path(r"d:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(server_path))

from app.parser.cst_manager import CSTParserManager

cst = CSTParserManager.get_instance()

def inspect_node_fields(node, source_bytes, title):
    print(f"\n--- {title} ---")
    print(f"Node type: {node.type}")
    print(f"Text: {cst.get_node_text(node, source_bytes)}")
    print(f"Child count: {len(node.children)}")
    for i, child in enumerate(node.children):
        # find field name if any
        field = node.field_name_for_child(i)
        print(f"  [{i}] field={field!r} type={child.type!r} text={repr(cst.get_node_text(child, source_bytes))}")

# 1. Python Subscripts
code_py = "x = container[0]\ny = data['key']\nz = text[1:5]\nw = matrix[i, j]"
source_py = code_py.encode("utf-8")
tree_py = cst.parse(code_py, "python")
for stmt in tree_py.root_node.children:
    if stmt.type == "expression_statement":
        assign = stmt.children[0]
        rhs = assign.child_by_field_name("right")
        inspect_node_fields(rhs, source_py, f"Python Subscript: {cst.get_node_text(rhs, source_py)}")

# 2. JS / TS Subscripts
code_js = "const x = container[0]; const y = data['key']; const z = matrix[i][j]; const opt = data?.[0];"
source_js = code_js.encode("utf-8")
tree_js = cst.parse(code_js, "javascript")
for stmt in tree_js.root_node.children:
    if stmt.type in ("lexical_declaration", "variable_declaration"):
        decl = stmt.children[1] # variable_declarator
        val = decl.child_by_field_name("value")
        inspect_node_fields(val, source_js, f"JS Subscript: {cst.get_node_text(val, source_js)}")

code_ts = "const opt = data?.[0]; const x = container[0];"
source_ts = code_ts.encode("utf-8")
tree_ts = cst.parse(code_ts, "typescript")
for stmt in tree_ts.root_node.children:
    if stmt.type in ("lexical_declaration", "variable_declaration"):
        decl = stmt.children[1]
        val = decl.child_by_field_name("value")
        inspect_node_fields(val, source_ts, f"TS Subscript: {cst.get_node_text(val, source_ts)}")
