import tree_sitter
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_python

js_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_javascript.language()))
ts_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_typescript.language_typescript()))
py_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))

def inspect(tree, code):
    print("--------------------------------------------------")
    print("CODE:", code.decode())
    def walk(n, depth=0):
        f = ""
        if n.parent:
            for i, c in enumerate(n.parent.children):
                if c == n:
                    fn = n.parent.field_name_for_child(i)
                    if fn: f = f" (field: {fn})"
                    break
        text = code[n.start_byte:n.end_byte].decode("utf-8", errors="replace").strip().replace("\n", " ")
        if len(text) > 40: text = text[:37] + "..."
        print(f"{'  '*depth}- {n.type}{f} [{n.start_point.row}:{n.start_point.column} - {n.end_point.row}:{n.end_point.column}] -> {text}")
        for c in n.children:
            walk(c, depth+1)
    walk(tree.root_node)

js_cases = [
    b"const { a } = obj;",
    b"const { a, b, c } = obj;",
    b"const { a: x, b: y } = obj;",
    b"const { a = 1, b: c = 2 } = obj;",
    b"const { a: { b: { c } } } = obj;",
    b"const { a, ...rest } = obj;",
    b"const [ x, y ] = arr;",
    b"const [ first, ...tail ] = arr;",
    b"const [ a, , c ] = arr;",  # elision / holes
    b"const [ a = 5, [ b, c ] ] = arr;",
    b"let a, b; ({ a, b } = obj);",
    b"let x, y; [ x, y ] = arr;",
    b"function foo({ x, y: z = 10, ...others }) {}",
    b"const fn = ([ a, { b } ]) => {};"
]

ts_cases = [
    b"const { a, b: c }: MyType = obj;",
    b"const [ first, second ]: [string, number] = arr;",
    b"function handle({ req, res }: Context) {}",
]

py_cases = [
    b"a, b = pair",
    b"(a, b) = pair",
    b"[a, b] = pair",
    b"a, b, c = triple",
    b"a, *b, c = seq",
    b"(a, (b, c)) = nested",
    b"[a, [b, c]] = nested",
    b"for u, v in edges: pass",
]

print("=== JAVASCRIPT PATTERNS ===")
for c in js_cases:
    inspect(js_parser.parse(c), c)

print("\n=== TYPESCRIPT PATTERNS ===")
for c in ts_cases:
    inspect(ts_parser.parse(c), c)

print("\n=== PYTHON PATTERNS ===")
for c in py_cases:
    inspect(py_parser.parse(c), c)
