import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
from typing import Dict, Any, Optional, Tuple

PY_LANG = tree_sitter.Language(tree_sitter_python.language())
JS_LANG = tree_sitter.Language(tree_sitter_javascript.language())

class CSTProgramSlicer:
    def __init__(self):
        self.py_parser = tree_sitter.Parser(PY_LANG)
        self.js_parser = tree_sitter.Parser(JS_LANG)

    def slice_enclosing_function(
        self,
        code: str,
        language: str,
        sink_line: int
    ) -> Dict[str, Any]:
        """
        Extracts the full enclosing function/method around the sink line.
        sink_line is 1-indexed.
        """
        code_bytes = code.encode("utf-8")
        parser = self.py_parser if language == "python" else self.js_parser
        tree = parser.parse(code_bytes)

        # Convert line to 0-indexed row for tree-sitter
        target_row = sink_line - 1

        # Find the leaf node at sink line
        leaf = tree.root_node.descendant_for_point_range(
            tree_sitter.Point(target_row, 0),
            tree_sitter.Point(target_row, 80)
        )

        fn_node_types = {
            "python": {"function_definition", "async_function_definition"},
            "javascript": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
            "typescript": {"function_declaration", "method_definition", "arrow_function", "function_expression"}
        }.get(language, {"function_definition"})

        curr = leaf
        enclosing_fn = None
        while curr:
            if curr.type in fn_node_types:
                enclosing_fn = curr
                break
            curr = curr.parent

        if not enclosing_fn:
            # Fallback to whole root
            enclosing_fn = tree.root_node

        func_bytes = code_bytes[enclosing_fn.start_byte:enclosing_fn.end_byte]
        func_code = func_bytes.decode("utf-8")

        # Extract function name and parameters
        fn_name = "anonymous"
        params = []
        for child in enclosing_fn.children:
            if child.type in {"identifier", "property_identifier"}:
                fn_name = code_bytes[child.start_byte:child.end_byte].decode("utf-8")
            elif child.type in {"parameters", "formal_parameters"}:
                for p in child.children:
                    if p.type in {"identifier", "typed_parameter", "formal_parameter"}:
                        # Extract parameter name
                        p_name = code_bytes[p.start_byte:p.end_byte].decode("utf-8")
                        params.append(p_name)

        return {
            "function_name": fn_name,
            "parameters": params,
            "start_line": enclosing_fn.start_point.row + 1,
            "end_line": enclosing_fn.end_point.row + 1,
            "start_byte": enclosing_fn.start_byte,
            "end_byte": enclosing_fn.end_byte,
            "slice_code": func_code,
            "node_type": enclosing_fn.type
        }

# Test with Python sample
py_sample = """import sqlite3

def find_user_by_id(user_id: int):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchone()

def helper():
    pass
"""

slicer = CSTProgramSlicer()
res_py = slicer.slice_enclosing_function(py_sample, "python", sink_line=7)
print("Python Slice Result:")
print("Function Name:", res_py["function_name"])
print("Lines:", res_py["start_line"], "to", res_py["end_line"])
print("Parameters:", res_py["parameters"])
print("Extracted Slice:\n" + res_py["slice_code"])

# Test with JavaScript sample
js_sample = """const { Client } = require('pg');

async function getUserProfile(req, res) {
    const userId = req.query.id;
    const client = new Client();
    await client.connect();
    const query = "SELECT * FROM profiles WHERE user_id = '" + userId + "'";
    const result = await client.query(query);
    res.json(result.rows);
}
"""

res_js = slicer.slice_enclosing_function(js_sample, "javascript", sink_line=8)
print("\nJS Slice Result:")
print("Function Name:", res_js["function_name"])
print("Lines:", res_js["start_line"], "to", res_js["end_line"])
print("Parameters:", res_js["parameters"])
print("Extracted Slice:\n" + res_js["slice_code"])
