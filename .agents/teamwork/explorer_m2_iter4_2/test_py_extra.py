import tree_sitter
import tree_sitter_python

py_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))

def walk(n, indent=0):
    if n.is_named:
        print(' '*indent, n.type, repr(n.text))
    for c in n.children:
        walk(c, indent+2)

print("=== Walrus operator ===")
tree = py_parser.parse(b'if (user := req.args.get("data")):\n    pass\n')
walk(tree.root_node)

print("\n=== Multi-target assignment ===")
tree = py_parser.parse(b'a = b = req.args.get("data")\n')
walk(tree.root_node)
