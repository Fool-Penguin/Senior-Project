import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript

py_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
js_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_javascript.language()))
ts_parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_typescript.language_typescript()))

def extract_pattern_targets(node: tree_sitter.Node):
    if node is None:
        return []
    node_type = node.type
    if node_type in (
        "identifier",
        "shorthand_property_identifier",
        "shorthand_property_identifier_pattern",
    ):
        return [node]
    if node_type == "pair_pattern":
        val_node = node.child_by_field_name("value")
        return extract_pattern_targets(val_node) if val_node else []
    if node_type in ("assignment_pattern", "object_assignment_pattern"):
        left_node = node.child_by_field_name("left")
        return extract_pattern_targets(left_node) if left_node else []
    if node_type in ("rest_pattern", "list_splat_pattern", "list_splat"):
        targets = []
        for child in node.children:
            if child.is_named:
                targets.extend(extract_pattern_targets(child))
        return targets
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
                targets.extend(extract_pattern_targets(child))
        return targets
    return []

test_cases = [
    # (lang, parser, code, expected_vars)
    ("JS", js_parser, "const { term } = req.query;", ["term"]),
    ("JS", js_parser, "const { a, b, c } = req.query;", ["a", "b", "c"]),
    ("JS", js_parser, "const { id: userId } = req.params;", ["userId"]),
    ("JS", js_parser, "const { term = 'def' } = req.query;", ["term"]),
    ("JS", js_parser, "const { id: userId = 1 } = req.params;", ["userId"]),
    ("JS", js_parser, "const { user: { name } } = req.body;", ["name"]),
    ("JS", js_parser, "const { a, ...rest } = req.query;", ["a", "rest"]),
    ("JS", js_parser, "const [ a, b ] = items;", ["a", "b"]),
    ("JS", js_parser, "const [ first, ...tail ] = items;", ["first", "tail"]),
    ("JS", js_parser, "const [ a, , c ] = items;", ["a", "c"]),
    ("JS", js_parser, "const [ a = 5, [ b, c ] ] = items;", ["a", "b", "c"]),
    ("JS", js_parser, "const { 'quoted-key': alias } = req.query;", ["alias"]),
    ("JS", js_parser, "const { [computed]: dynAlias } = req.query;", ["dynAlias"]),
    ("TS", ts_parser, "const { id: userId }: any = req.params;", ["userId"]),
    ("TS", ts_parser, "const [ a, b ]: string[] = items;", ["a", "b"]),
    ("PY", py_parser, "user, status = req.args.get('data')", ["user", "status"]),
    ("PY", py_parser, "(user, status) = req.args.get('data')", ["user", "status"]),
    ("PY", py_parser, "[user, status] = req.args.get('data')", ["user", "status"]),
    ("PY", py_parser, "user, *rest = req.args.get('data')", ["user", "rest"]),
    ("PY", py_parser, "a, (b, c) = req.args.get('data')", ["a", "b", "c"]),
    ("PY", py_parser, "[a, [b, c]] = req.args.get('data')", ["a", "b", "c"]),
]

all_passed = True
for lang, parser, code, expected in test_cases:
    tree = parser.parse(code.encode("utf-8"))
    root = tree.root_node
    # find declarator name or assignment left
    target_node = None
    for stmt in root.children:
        if stmt.type in ("lexical_declaration", "variable_declaration"):
            for decl in stmt.children:
                if decl.type == "variable_declarator":
                    target_node = decl.child_by_field_name("name")
        elif stmt.type == "expression_statement":
            for child in stmt.children:
                if child.type == "assignment":
                    target_node = child.child_by_field_name("left")
    
    extracted_nodes = extract_pattern_targets(target_node)
    extracted_names = [n.text.decode("utf-8") for n in extracted_nodes]
    if extracted_names == expected:
        print(f"[PASS] {lang}: {code} -> {extracted_names}")
    else:
        print(f"[FAIL] {lang}: {code} -> Got {extracted_names}, expected {expected}")
        all_passed = False

if all_passed:
    print("\nALL 21 TEST CASES PASSED PERFECTLY!")
