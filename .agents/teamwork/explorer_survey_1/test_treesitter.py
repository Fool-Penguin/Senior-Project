import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript

py_lang = tree_sitter.Language(tree_sitter_python.language())
py_parser = tree_sitter.Parser(py_lang)
print("Python parse:", py_parser.parse(b"def foo(): pass").root_node.type)

js_lang = tree_sitter.Language(tree_sitter_javascript.language())
js_parser = tree_sitter.Parser(js_lang)
print("JS parse:", js_parser.parse(b"function bar() {}").root_node.type)

ts_lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
ts_parser = tree_sitter.Parser(ts_lang)
print("TS parse:", ts_parser.parse(b"const x: number = 42;").root_node.type)

tsx_lang = tree_sitter.Language(tree_sitter_typescript.language_tsx())
tsx_parser = tree_sitter.Parser(tsx_lang)
print("TSX parse:", tsx_parser.parse(b"const el = <div>hello</div>;").root_node.type)
