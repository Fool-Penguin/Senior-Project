import tree_sitter
import tree_sitter_python

py_lang = tree_sitter.Language(tree_sitter_python.language())
py_parser = tree_sitter.Parser(py_lang)

bad_code = b"""
def broken_syntax(x, y
    return x +
"""

tree = py_parser.parse(bad_code)
print("has_error:", tree.root_node.has_error)

def find_errors(node):
    errors = []
    if node.is_error or node.is_missing:
        errors.append((node.type, node.start_point, node.end_point))
    for child in node.children:
        errors.extend(find_errors(child))
    return errors

print("Detected errors:", find_errors(tree.root_node))
