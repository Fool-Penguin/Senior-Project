"""Measure one Python / JavaScript / TypeScript source file with tree-sitter.

measure(path, source_bytes) -> FileResult (file SLOC/CLOC, units, import specifiers) or None on parse error.

Definitions (see README.md for the reasoning):
- Unit (function): Python def/async def (a lambda belongs to its enclosing def, as in SonarQube);
  JS/TS function declaration/expression, arrow function, generator, method.
  Every node belongs to its innermost unit for cyclomatic, SLOC and params.
- Python nested def, as SonarQube does it:
  Cyclomatic: per function, nested defs measured separately (sonar-python cyclomatic rule).
  Cognitive: nested defs folded into the enclosing function (sonar-python cognitive rule); nested defs have no
  cognitive value (None, blank in functions.csv), because SonarQube does not report one [RUN].
- Cognitive SLOC: rows the cognitive score covers (own rows + folded nested defs, each row once); the weight
  of cognitive in derive.py. Equals SLOC for JS/TS and for Python functions without nested defs.
- SLOC: rows holding at least one code token. Python docstrings are comments, not code.
- CLOC: rows holding comment text with at least one letter/digit (Sonar comment_lines rule).
  Commented-out code counts. A leading license/copyright comment block does not count.
- Cyclomatic: 1 + decision points, as SonarQube counts them.
  Python (sonar-python ComplexityVisitor): if (not elif), for, while, conditional expression, and/or,
  comprehension if (not a `case` guard). JS/TS (SonarJS S1541): if (else if included), for/for-in/for-of,
  while, do, case (not default), ternary, each &&/||/??.
- Cognitive: SonarSource white paper (G. Ann Campbell) as implemented by SonarQube: no recursion increment;
  JS/TS: `||` and `??` add nothing anywhere, also in an `if` condition [SRC+RUN], an `&&` adds 1 unless the
  operator before it in the chain is also `&&`, and a single-operator chain directly inside a JSX expression
  adds nothing (SonarJS S3776).
  Nesting: only bodies nest (loop body, ternary branches, switch cases, catch/except body); a loop header,
  ternary test, switch value and except value stay at the current level [SRC+RUN]. Python exceptions
  (sonar-python [RUN]): a conditional expression nests its condition too; a lambda adds no nesting; `match`
  adds 0 (case bodies nest); `try ... else` adds +1.
- Params: declared parameters; Python self/cls (first parameter) and TS `this:` are not counted.
"""
import re
from dataclasses import dataclass, field

from tree_sitter_language_pack import get_parser

LANGUAGE = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
            ".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "typescript"}
GRAMMAR = {".py": "python", ".tsx": "tsx", ".ts": "typescript", ".mts": "typescript", ".cts": "typescript"}  # rest: javascript

PY_UNITS = {"function_definition"}
JS_UNITS = {"function_declaration", "function_expression", "function", "generator_function_declaration",
            "generator_function", "arrow_function", "method_definition"}
LOGICAL = {"&&", "||", "??", "and", "or"}
# SonarQube Python: no elif, except, case, comprehension for, else
PY_DECISIONS = {"if_statement", "for_statement", "while_statement", "conditional_expression", "boolean_operator",
                "if_clause"}
# SonarJS S1541: no catch, default, logical assignment, optional chaining (logical &&/||/?? added separately)
JS_DECISIONS = {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement",
                "switch_case", "ternary_expression"}
LICENSE = re.compile(r"copyright|licen[cs]e|spdx-license-identifier", re.I)
SIGNIFICANT = re.compile(r"[^\W_]")  # a letter or digit


@dataclass
class Unit:
    name: str
    kind: str
    start_line: int
    end_line: int
    sloc: int
    cyclomatic: int
    cognitive: int | None  # None: Python nested def (counted in the enclosing function)
    params: int
    cognitive_sloc: int | None = None  # SLOC the cognitive score covers: own rows + folded nested defs


@dataclass
class FileResult:
    language: str
    sloc: int
    cloc: int
    units: list = field(default_factory=list)
    imports: list = field(default_factory=list)  # Python: (level, module, names); JS/TS: specifier strings
    # parallel to imports: True = type-only (Python `if TYPE_CHECKING:`, TS `import type` / all names `type`)
    type_only: list = field(default_factory=list)


def _op(node):
    op = node.child_by_field_name("operator")
    return op.type if op is not None else None


def _is_logical(node):
    return node.type in ("boolean_operator", "binary_expression") and _op(node) in LOGICAL


def _rows(node):
    """Rows touched by a node; a token ending at column 0 does not touch its last row."""
    end = node.end_point[0] - (node.end_point[1] == 0 and node.end_point[0] > node.start_point[0])
    return range(node.start_point[0], end + 1)


def _docstrings(root):
    """First-statement string literals of module / class / function bodies (Python)."""
    found = set()
    for body in [root] + [n.child_by_field_name("body") for n in _walk(root)
                          if n.type in ("function_definition", "class_definition")]:
        first = next((c for c in (body.named_children if body else []) if c.type != "comment"), None)
        if first is not None and first.type == "expression_statement" and first.named_child_count == 1:
            first = first.named_children[0]
        if first is not None and first.type == "string":
            found.add(first.id)
    return found


def _walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _unit_name(node):
    name = node.child_by_field_name("name")
    if name is not None:
        return name.text.decode("utf-8", "replace")
    parent = node.parent
    if parent is not None and parent.type in ("variable_declarator", "public_field_definition", "pair",
                                              "assignment_expression", "assignment", "field_definition"):
        target = (parent.child_by_field_name("name") or parent.child_by_field_name("key")
                  or parent.child_by_field_name("property") or parent.child_by_field_name("left"))
        if target is not None:
            return target.text.decode("utf-8", "replace").split(".")[-1]
    return "<anonymous>"


def _params(node, python):
    plist = node.child_by_field_name("parameters")
    if plist is None:
        return 1 if node.child_by_field_name("parameter") is not None else 0  # `x => ...`
    params = [p for p in plist.named_children
              if p.type not in ("comment", "keyword_separator", "positional_separator")]
    if python and node.type == "function_definition" and params:
        first = params[0] if params[0].type == "identifier" else params[0].named_children[0]
        if first.text in (b"self", b"cls"):
            params = params[1:]
    if not python:
        params = [p for p in params if not (p.named_child_count and p.named_children[0].type == "this")]
    return len(params)


def _in_order_ops(node, transparent=True):
    """In-order operator list of a logical chain. JS/TS: parentheses are transparent. Python: a parenthesized
    group is a separate operand, counted as its own chain (SonarQube [RUN] 2026-11-02: `a and (b or c) and d`
    = +2, not +3)."""
    out = []

    def strip(n):
        while transparent and n.type == "parenthesized_expression" and n.named_child_count == 1:
            n = n.named_children[0]
        return n

    stack = [(node, False)]
    while stack:
        n, expanded = stack.pop()
        n = strip(n)
        if not _is_logical(n):
            continue
        if expanded:
            out.append(_op(n))
            continue
        stack.append((n.child_by_field_name("right"), False))
        stack.append((n, True))
        stack.append((n.child_by_field_name("left"), False))
    return out


def _logical_operands(node, transparent=True):
    out, stack = [], [node]
    while stack:
        n = stack.pop()
        inner = n
        while transparent and inner.type == "parenthesized_expression" and inner.named_child_count == 1:
            inner = inner.named_children[0]
        if _is_logical(inner):
            stack.append(inner.child_by_field_name("right"))
            stack.append(inner.child_by_field_name("left"))
        else:
            out.append(n)
    return out


def _jsx_parent(node):
    """Logical chain written directly in a JSX expression `{a && b}` (parentheses are transparent)."""
    parent = node.parent
    while parent is not None and parent.type == "parenthesized_expression":
        parent = parent.parent
    return parent is not None and parent.type == "jsx_expression"


def _strip_parens(n):
    while n is not None and n.type == "parenthesized_expression" and n.named_child_count == 1:
        n = n.named_children[0]
    return n


STRUCTURES = {"for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement",
              "conditional_expression", "ternary_expression", "except_clause", "catch_clause"}
BODY_FIELDS = {"body", "consequence", "alternative"}


def _py_def_nesting(node, nest):
    """Nesting level inside a Python `def` folded into its enclosing function (sonar-python NestingLevel,
    [RUN] 2026-11-05): one level deeper; a def directly in a class body starts at 0; a "wrapper" def (the
    enclosing function's other statements are only `return <name>`) keeps the current level."""
    stmt = node.parent if node.parent.type == "decorated_definition" else node
    block = stmt.parent
    owner = block.parent if block.type == "block" else None
    if owner is not None and owner.type == "class_definition":
        return 0
    if owner is not None and owner.type == "function_definition" and all(
            s.type == "return_statement" and s.named_child_count == 1 and s.named_children[0].type == "identifier"
            for s in block.named_children if s != stmt and s.type != "comment"):
        return nest
    return nest + 1


def _cognitive(unit, python, units):
    """Cognitive complexity of one unit.
    JS/TS: nested functions are skipped (measured on their own).
    Python: a nested `def` is part of the enclosing function, one nesting level deeper (SonarQube [RUN] on
    real code, 2026-11-02; exceptions in _py_def_nesting)."""
    total = 0
    # SonarJS quirk [RUN 2026-11-02]: a ternary whose branch IS a function (`a ? () => g() : null`) raises the
    # nesting level by 1 for every structure after that ternary, until the end of the enclosing function.
    bumps = []  # end bytes of such ternaries

    def extra(n):
        return sum(n.start_byte >= e for e in bumps)

    stack = [(c, 0) for c in reversed(unit.children)]
    while stack:
        node, nest = stack.pop()
        t = node.type
        if node.id != unit.id and node.type in units:
            if python:
                inner = _py_def_nesting(node, nest)
                stack.extend(reversed([(c, inner) for c in node.named_children]))
            continue
        push = []  # (child, nesting) in source order
        if t == "if_statement":
            total += 1 + nest + extra(node)
            cur = node
            while cur is not None:
                nxt = None
                for c in cur.children:
                    if c.type == "elif_clause":
                        total += 1
                        push += [(c.child_by_field_name("condition"), nest),
                                 (c.child_by_field_name("consequence"), nest + 1)]
                    elif c.type == "else_clause":
                        body = [x for x in c.named_children if x.type != "comment"]
                        if not python and len(body) == 1 and body[0].type == "if_statement":
                            total += 1  # `else if`: hybrid increment, no nesting penalty
                            nxt = body[0]
                        else:
                            total += 1
                            push += [(x, nest + 1) for x in c.named_children]
                    elif c == cur.child_by_field_name("consequence"):
                        push.append((c, nest + 1))
                    elif c.is_named:
                        push.append((c, nest))
                cur = nxt
        elif t in STRUCTURES:
            total += 1 + nest + extra(node)
            if t == "conditional_expression":  # sonar-python nests the whole expression, condition included
                push = [(c, nest + 1) for c in node.named_children]
            else:  # only bodies nest: loop header, ternary test, switch value, except/catch value stay [RUN]
                push = [(c, nest + 1 if node.field_name_for_child(i) in BODY_FIELDS
                         or (t == "except_clause" and c.type == "block") else nest)
                        for i, c in enumerate(node.children) if c.is_named]
            if t == "ternary_expression":
                bumps += [node.end_byte for f in ("consequence", "alternative")
                          if _strip_parens(node.child_by_field_name(f)) is not None
                          and _strip_parens(node.child_by_field_name(f)).type in units]
            # Python `for ... else` / `while ... else`: +1 like `else` (matches SonarQube on probe_brain.py)
            total += sum(c.type == "else_clause" for c in node.named_children)
        elif _is_logical(node):
            ops = _in_order_ops(node, transparent=not python)
            if python:  # white paper: +1 per run of identical operators
                total += 1 + sum(a != b for a, b in zip(ops, ops[1:]))
            elif not (_jsx_parent(node) and len(set(ops)) == 1):  # SonarJS: only && runs count
                total += sum(op == "&&" and (i == 0 or ops[i - 1] != "&&") for i, op in enumerate(ops))
            push = [(c, nest) for c in _logical_operands(node, transparent=not python)]
        elif python and t in ("case_clause", "try_statement"):
            # sonar-python [RUN]: `match` adds 0 but case bodies nest; `try ... else` adds +1 and the else body
            # nests; try/finally bodies do not nest
            total += sum(c.type == "else_clause" for c in node.children)
            push = [(c, nest + 1 if node.field_name_for_child(i) == "consequence" or c.type == "else_clause"
                     else nest) for i, c in enumerate(node.children) if c.is_named]
        elif t in ("break_statement", "continue_statement") and any(
                c.type == "statement_identifier" for c in node.children):
            total += 1
        else:  # recursion adds nothing (Python [RUN], JS/TS [SRC+RUN]); a Python lambda adds no nesting [RUN]
            push = [(c, nest) for c in node.named_children]
        stack.extend(reversed([p for p in push if p[0] is not None]))
    return total


def measure(path, source):
    ext = path[path.rfind("."):].lower()
    python = ext == ".py"
    if source.startswith(b"\xef\xbb\xbf"):
        source = source[3:]
    tree = get_parser(GRAMMAR.get(ext, "javascript")).parse(source)
    root = tree.root_node
    if root.has_error:
        return None
    unit_types = PY_UNITS if python else JS_UNITS
    decisions = PY_DECISIONS if python else JS_DECISIONS
    docstrings = _docstrings(root) if python else set()

    # License header: the leading comments (and the Python module docstring) are split into blocks: one
    # `/* */` comment or docstring, or a run of line comments on consecutive rows. Only blocks that mention
    # copyright/licence are excluded, so a following `/** @file ... */` still counts.
    # A shebang line is neither code nor comment.
    shebang = source.startswith(b"#!")
    blocks = []
    for c in root.children:
        node = c.named_children[0] if c.type == "expression_statement" and c.named_child_count == 1 else c
        if node.id in docstrings:
            blocks.append([node])
            continue
        if c.type not in ("comment", "hash_bang_line"):
            break
        prev = blocks[-1][-1] if blocks else None
        if prev is not None and c.text.startswith((b"#", b"//")) and prev.text.startswith((b"#", b"//")) \
                and c.start_point[0] == prev.end_point[0] + 1:
            blocks[-1].append(c)
        else:
            blocks.append([c])
    header_rows = {r for b in blocks if LICENSE.search(b"\n".join(n.text for n in b).decode("utf-8", "replace"))
                   for n in b for r in _rows(n)}

    code_rows, comment_rows = set(), set()
    unit_rows = {}  # unit node id -> rows
    unit_nodes = []
    stack = [(root, None)]
    result = FileResult(LANGUAGE[ext], 0, 0)
    cyclo = {}
    while stack:
        node, unit = stack.pop()
        # is_named: the `function` KEYWORD token also has type "function" and must not become a unit
        if node.is_named and node.type in unit_types and node is not root:
            unit = node
            unit_nodes.append(node)
            unit_rows[node.id] = set()
            cyclo[node.id] = 1
        if node.type in ("comment", "hash_bang_line") or node.id in docstrings:
            lines = node.text.decode("utf-8", "replace").split("\n")
            for r in _rows(node):
                if r not in header_rows and SIGNIFICANT.search(lines[r - node.start_point[0]]) \
                        and not (shebang and r == 0):
                    comment_rows.add(r)
            continue
        if unit is not None:
            t = node.type
            # a `case ... if guard:` is an if_clause too, but sonar-python counts only comprehension ifs
            if (t in decisions and not (t == "if_clause" and node.parent.type == "case_clause")) \
                    or (t == "binary_expression" and _op(node) in LOGICAL):
                cyclo[unit.id] += 1
        if node.child_count == 0:
            if node.start_byte != node.end_byte:
                rows = _rows(node)
                code_rows.update(rows)
                if unit is not None:
                    unit_rows[unit.id].update(rows)
            continue
        _collect_import(node, python, result)
        stack.extend((c, unit) for c in reversed(node.children))

    if shebang:
        code_rows.discard(0)
    result.sloc = len(code_rows)
    result.cloc = len(comment_rows)
    # rows each cognitive score covers: a Python nested def's rows go to the outermost def around it (the one
    # whose cognitive includes it); a row shared by both is counted once
    cognitive_rows = {u.id: set(unit_rows[u.id]) for u in unit_nodes}
    for u in unit_nodes:
        owner, p = None, u.parent
        while python and p is not None:
            if p.type == "function_definition":
                owner = p
            p = p.parent
        if owner is not None:
            cognitive_rows[owner.id] |= unit_rows[u.id]
            cognitive_rows[u.id] = None
    for u in sorted(unit_nodes, key=lambda n: n.start_byte):
        name = _unit_name(u)
        # Python nested def: its cognitive is counted in the enclosing function, it has none of its own
        nested = cognitive_rows[u.id] is None
        cognitive = None if nested else _cognitive(u, python, unit_types)
        result.units.append(Unit(name, u.type, u.start_point[0] + 1, u.end_point[0] + 1, len(unit_rows[u.id]),
                                 cyclo[u.id], cognitive, _params(u, python),
                                 None if nested else len(cognitive_rows[u.id])))
    return result


def measure_snippet(path, source):
    """measure() for a code fragment, e.g. one function. A JS/TS class method on its own (`f(a) { ... }`) is not
    valid code, so it is retried inside `class _ {` ... `}`; lines and SLOC are corrected for the two added rows.
    Only for single fragments: the derivation pipeline uses measure(), where such a file is a parse error."""
    source = source.removeprefix(b"\xef\xbb\xbf")
    result = measure(path, source)
    if result is not None or path.lower().endswith(".py"):
        return result
    result = measure(path, b"class _ {\n" + source + b"\n}")
    if result is None:
        return None
    result.sloc -= 2
    for u in result.units:
        u.start_line -= 1
        u.end_line -= 1
    return result


def _string_value(node):
    """Value of a plain string literal (no interpolation), else None."""
    if node is None or node.type != "string":
        return None
    parts = [c for c in node.named_children if c.type not in ("string_start", "string_end")]
    if len(parts) == 1 and parts[0].type in ("string_fragment", "string_content"):
        return parts[0].text.decode("utf-8", "replace")
    return None


def _type_checking(node):
    """Inside the body of `if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:` (its elif/else run normally)."""
    child, p = node, node.parent
    while p is not None:
        if p.type == "if_statement" and p.child_by_field_name("consequence") == child \
                and p.child_by_field_name("condition").text.split(b".")[-1] == b"TYPE_CHECKING":
            return True
        child, p = p, p.parent
    return False


def _js_type_only(node):
    """`import type ...` / `export type ...`, or every imported/exported name marked `type`."""
    if any(c.type == "type" for c in node.children):
        return True
    clause = next((c for c in node.named_children if c.type in ("import_clause", "export_clause")), None)
    if clause is None:
        return False
    if clause.type == "import_clause":
        if any(c.type != "named_imports" for c in clause.named_children):
            return False  # a default or namespace import is a value
        specs = [s for c in clause.named_children for s in c.named_children if s.type == "import_specifier"]
    else:
        specs = [s for s in clause.named_children if s.type == "export_specifier"]
    return bool(specs) and all(any(x.type == "type" for x in s.children) for s in specs)


def _collect_import(node, python, result):
    t = node.type

    def add(item, type_only=False):
        result.imports.append(item)
        result.type_only.append(type_only)

    if python:
        if t == "import_statement":
            for n in node.children_by_field_name("name"):
                dotted = n.child_by_field_name("name") if n.type == "aliased_import" else n
                add((0, dotted.text.decode(), []), _type_checking(node))
        elif t == "import_from_statement":
            mod = node.child_by_field_name("module_name")
            level, module = 0, ""
            if mod.type == "relative_import":
                prefix = next(c for c in mod.children if c.type == "import_prefix")
                level = len(prefix.text)
                dotted = next((c for c in mod.children if c.type == "dotted_name"), None)
                module = dotted.text.decode() if dotted is not None else ""
            else:
                module = mod.text.decode()
            names = []
            for n in node.children_by_field_name("name"):
                dotted = n.child_by_field_name("name") if n.type == "aliased_import" else n
                names.append(dotted.text.decode())
            add((level, module, names), _type_checking(node))
        elif t == "call":
            fn = node.child_by_field_name("function")
            args = node.child_by_field_name("arguments")
            fname = fn.text.split(b".")[-1] if fn is not None else b""
            if fname in (b"import_module", b"__import__") and args is not None and args.named_child_count:
                value = _string_value(args.named_children[0])
                if value and not value.startswith("."):
                    add((0, value, []))
        return
    if t in ("import_statement", "export_statement"):
        value = _string_value(node.child_by_field_name("source"))
        if value is None and t == "import_statement":  # import x = require("y")
            req = next((c for c in node.named_children if c.type == "import_require_clause"), None)
            value = _string_value(next((c for c in req.named_children if c.type == "string"), None)) if req else None
        if value:
            add(value, _js_type_only(node))
    elif t == "call_expression":
        fn = node.child_by_field_name("function")
        args = node.child_by_field_name("arguments")
        if fn is not None and (fn.type == "import" or fn.text == b"require") and args is not None \
                and args.named_child_count:
            value = _string_value(args.named_children[0])
            if value:
                add(value)
