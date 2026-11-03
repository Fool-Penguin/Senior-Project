import tree_sitter
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_python

js_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_javascript.language()))
ts_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_typescript.language_typescript()))
py_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))

def dump(node, source, indent=0):
    text = source[node.start_byte:node.end_byte].decode('utf-8', errors='replace')
    first_line = text.splitlines()[0] if text else ''
    if len(first_line) > 50:
        first_line = first_line[:50] + '...'
    field = ''
    if node.parent:
        # find field name if any
        for i, child in enumerate(node.parent.children):
            if child == node:
                fn = node.parent.field_name_for_child(i)
                if fn:
                    field = f' [{fn}]'
                break
    print('  ' * indent + f'{node.type}{field}: {first_line}')
    for child in node.children:
        dump(child, source, indent + 1)

cases = [
    ('JS', js_parser, b'const { term } = req.query;'),
    ('JS', js_parser, b'const { id: userId } = req.params;'),
    ('JS', js_parser, b'const { term = "def" } = req.query;'),
    ('JS', js_parser, b'const { user: { name } } = req.body;'),
    ('JS', js_parser, b'const { a, ...rest } = req.query;'),
    ('JS', js_parser, b'const [ a, b ] = items;'),
    ('JS', js_parser, b'const [ first, ...rest ] = items;'),
    ('JS', js_parser, b'const [ x = 1 ] = items;'),
    ('JS', js_parser, b'({ term } = req.query);'),
    ('JS', js_parser, b'({ id: userId } = req.params);'),
    ('JS', js_parser, b'[ a, b ] = items;'),
    ('TS', ts_parser, b'const { term }: { term: string } = req.query;'),
    ('TS', ts_parser, b'const { id: userId }: any = req.params;'),
    ('TS', ts_parser, b'const [ a, b ]: string[] = items;'),
    ('PY', py_parser, b'user, status = req.args.get("data")'),
    ('PY', py_parser, b'(user, status) = req.args.get("data")'),
    ('PY', py_parser, b'[user, status] = req.args.get("data")'),
    ('PY', py_parser, b'user, *rest = req.args.get("data")'),
    ('PY', py_parser, b'a, (b, c) = req.args.get("data")'),
]

for label, parser, code in cases:
    print(f"\n==================== {label}: {code.decode()} ====================")
    tree = parser.parse(code)
    dump(tree.root_node, code)
