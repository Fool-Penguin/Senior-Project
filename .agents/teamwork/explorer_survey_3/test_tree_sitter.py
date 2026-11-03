import tree_sitter
import tree_sitter_python
import tree_sitter_javascript

print('tree_sitter version:', tree_sitter.__version__)
py_lang = tree_sitter.Language(tree_sitter_python.language())
js_lang = tree_sitter.Language(tree_sitter_javascript.language())
py_parser = tree_sitter.Parser(py_lang)
js_parser = tree_sitter.Parser(js_lang)

py_code = b"""
def get_user(user_id: int):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
"""
py_tree = py_parser.parse(py_code)
print('Python root:', py_tree.root_node.type, 'has_error:', py_tree.root_node.has_error)

js_code = b"""
function getUser(req, res) {
    const id = req.query.id;
    const query = "SELECT * FROM users WHERE id = '" + id + "'";
    db.query(query);
}
"""
js_tree = js_parser.parse(js_code)
print('JS root:', js_tree.root_node.type, 'has_error:', js_tree.root_node.has_error)

# Test finding function definition and its children
def print_cst(node, depth=0):
    indent = "  " * depth
    print(f"{indent}{node.type} [{node.start_point} - {node.end_point}]")
    for child in node.children[:3]:
        print_cst(child, depth + 1)
    if len(node.children) > 3:
        print(f"{indent}  ... ({len(node.children) - 3} more children)")

print("\n--- Python CST Function Definition ---")
func_node = py_tree.root_node.children[0]
print_cst(func_node)
