import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript

py_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
js_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_javascript.language()))
ts_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_typescript.language_typescript()))

def print_nodes(node, indent=0):
    text = repr(node.text[:30] if node.text else b'')
    print(f"{'  '*indent}{node.type} is_named={node.is_named} text={text}")
    for c in node.children:
        print_nodes(c, indent + 1)

print("=== Python splat ===")
tree = py_parser.parse(b'user, *rest = req.args.get("data")')
print_nodes(tree.root_node.children[0].children[0])

print("\n=== Python tuple ===")
tree = py_parser.parse(b'(user, status) = req.args.get("data")')
print_nodes(tree.root_node.children[0].children[0])

print("\n=== Python list ===")
tree = py_parser.parse(b'[user, status] = req.args.get("data")')
print_nodes(tree.root_node.children[0].children[0])
