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
    # Assignment expressions
    ("JS", js_parser, "({ term } = req.query);", ["term"]),
    ("JS", js_parser, "({ id: userId } = req.params);", ["userId"]),
    ("JS", js_parser, "[ a, b ] = items;", ["a", "b"]),
]

for lang, parser, code, expected in test_cases:
    tree = parser.parse(code.encode("utf-8"))
    root = tree.root_node
    # find assignment_expression left
    target_node = None
    for stmt in root.children:
        if stmt.type == "expression_statement":
            for child in stmt.children:
                if child.type == "parenthesized_expression":
                    for sub in child.children:
                        if sub.type == "assignment_expression":
                            target_node = sub.child_by_field_name("left")
                elif child.type == "assignment_expression":
                    target_node = child.child_by_field_name("left")
    
    extracted_nodes = extract_pattern_targets(target_node)
    extracted_names = [n.text.decode("utf-8") for n in extracted_nodes]
    if extracted_names == expected:
        print(f"[PASS] {lang}: {code} -> {extracted_names}")
    else:
        print(f"[FAIL] {lang}: {code} -> Got {extracted_names}, expected {expected}")
