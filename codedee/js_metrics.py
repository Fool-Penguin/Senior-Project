"""Function-level maintainability metrics for JavaScript / TypeScript.

Same gates as python_metrics.py (McCabe + Sonar-style cognitive).
Requires tree-sitter, tree-sitter-javascript, tree-sitter-typescript.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from codedee.python_metrics import FunctionMetrics, _findings

JS_SUFFIXES = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}

FUNCTION_TYPES = {
    "function_declaration",
    "function_expression",
    "generator_function_declaration",
    "generator_function",
    "arrow_function",
    "method_definition",
}

PARAM_TYPES = {
    "identifier",
    "assignment_pattern",
    "rest_pattern",
    "object_pattern",
    "array_pattern",
    "required_parameter",
    "optional_parameter",
    "rest_parameter",
    "object_binding_pattern",
    "array_binding_pattern",
}

LOOP_TYPES = {
    "for_statement",
    "for_in_statement",
    "while_statement",
    "do_statement",
}


class JsMetricsUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _languages() -> dict:
    try:
        from tree_sitter import Language
        import tree_sitter_javascript as tsjs
        import tree_sitter_typescript as tsts
    except ImportError as exc:
        raise JsMetricsUnavailable(
            "JS/TS scan needs tree-sitter, tree-sitter-javascript, and "
            "tree-sitter-typescript (see codedee/requirements.txt)"
        ) from exc
    return {
        "javascript": Language(tsjs.language()),
        "typescript": Language(tsts.language_typescript()),
        "tsx": Language(tsts.language_tsx()),
    }


def language_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if name.endswith(".d.ts") or name.endswith(".d.tsx"):
        return "typescript"
    if suffix == ".tsx":
        return "tsx"
    if suffix == ".ts":
        return "typescript"
    if suffix == ".jsx":
        return "javascript"
    return "javascript"


def is_js_source(path: Path) -> bool:
    if path.suffix.lower() not in JS_SUFFIXES:
        return False
    name = path.name.lower()
    if name.endswith(".d.ts") or name.endswith(".d.tsx"):
        return False
    if ".min." in name:
        return False
    return True


def _parser_for(path: Path):
    from tree_sitter import Parser

    langs = _languages()
    return Parser(langs[language_for_path(path)])


def _text(node) -> str:
    raw = node.text
    if raw is None:
        return ""
    return raw.decode("utf-8", errors="replace")


def _function_name(node) -> str:
    named = node.child_by_field_name("name")
    if named is not None:
        return _text(named) or "(anonymous)"
    if node.type == "method_definition":
        for i in range(node.child_count):
            child = node.children[i]
            field = node.field_name_for_child(i)
            if field == "name" or child.type in {
                "property_identifier",
                "private_property_identifier",
                "computed_property_name",
            }:
                return _text(child)
    parent = node.parent
    if parent is not None and parent.type == "variable_declarator":
        name = parent.child_by_field_name("name")
        if name is not None:
            return _text(name)
    if parent is not None and parent.type == "pair":
        key = parent.child_by_field_name("key")
        if key is not None:
            return _text(key)
        for child in parent.children:
            if child.type in {"property_identifier", "string", "identifier"} and child is not node:
                return _text(child).strip("\"'")
    if parent is not None and parent.type == "assignment_expression":
        left = parent.child_by_field_name("left")
        if left is not None:
            return _text(left)
    return "(anonymous)"


def _param_count(node) -> int:
    params = node.child_by_field_name("parameters")
    if params is None:
        # x => x
        for child in node.children:
            if child.type == "identifier":
                return 1
        return 0
    if params.type == "identifier":
        return 1
    return sum(1 for child in params.children if child.type in PARAM_TYPES)


def _sloc(node, source: str) -> tuple[int, int]:
    start = node.start_point[0] + 1
    end = node.end_point[0] + 1
    loc = end - start + 1
    lines = source.splitlines()[start - 1 : end]
    sloc = 0
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            continue
        if stripped.startswith("/*") and stripped.endswith("*/"):
            continue
        sloc += 1
    return loc, sloc


def _is_and_or(node) -> bool:
    if node.type != "binary_expression":
        return False
    op = node.child_by_field_name("operator")
    if op is None:
        for child in node.children:
            if _text(child) in {"&&", "||", "??"}:
                return True
        return False
    return _text(op) in {"&&", "||", "??"}


def _cyclomatic(node) -> int:
    score = 1

    def walk(cur) -> None:
        nonlocal score
        if cur.type in FUNCTION_TYPES and cur is not node:
            return
        if cur.type == "if_statement":
            score += 1
        elif cur.type in LOOP_TYPES:
            score += 1
        elif cur.type in {"catch_clause", "ternary_expression", "conditional_type"}:
            score += 1
        elif cur.type in {"switch_case", "switch_default"}:
            score += 1
        elif _is_and_or(cur):
            score += 1
        for child in cur.children:
            walk(child)

    body = node.child_by_field_name("body")
    walk(body if body is not None else node)
    return score


class _Cog:
    def __init__(self) -> None:
        self.score = 0
        self.nesting = 0
        self.max_nesting = 0

    def _bump(self) -> None:
        self.nesting += 1
        self.max_nesting = max(self.max_nesting, self.nesting)


def _cognitive(node) -> tuple[int, int]:
    state = _Cog()

    def walk(cur) -> None:
        if cur.type in FUNCTION_TYPES and cur is not node:
            return
        if cur.type == "if_statement":
            state.score += 1 + state.nesting
            cons = cur.child_by_field_name("consequence")
            alt = cur.child_by_field_name("alternative")
            state._bump()
            if cons is not None:
                walk(cons)
            state.nesting -= 1
            if alt is not None:
                # else if: alternative is else_clause wrapping if_statement
                inner = None
                for child in alt.children:
                    if child.type == "if_statement":
                        inner = child
                        break
                if inner is not None:
                    walk(inner)
                else:
                    state.score += 1
                    walk(alt)
            return
        if cur.type in LOOP_TYPES or cur.type in {"catch_clause", "switch_statement"}:
            state.score += 1 + state.nesting
            state._bump()
            for child in cur.children:
                walk(child)
            state.nesting -= 1
            return
        if cur.type == "ternary_expression":
            state.score += 1 + state.nesting
            for child in cur.children:
                walk(child)
            return
        if _is_and_or(cur):
            state.score += 1
        for child in cur.children:
            walk(child)

    body = node.child_by_field_name("body")
    walk(body if body is not None else node)
    return state.score, state.max_nesting


def _analyze_function(node, source: str, filename: str) -> FunctionMetrics:
    loc, sloc = _sloc(node, source)
    cc = _cyclomatic(node)
    cog, nest = _cognitive(node)
    m = FunctionMetrics(
        file=filename,
        function=_function_name(node),
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        loc=loc,
        sloc=sloc,
        params=_param_count(node),
        cyclomatic=cc,
        cognitive=cog,
        max_nesting=nest,
        findings=[],
    )
    m.findings = _findings(m)
    return m


def analyze_source(source: str, filename: str, path: Path | None = None) -> list[FunctionMetrics]:
    target = path or Path(filename)
    parser = _parser_for(target)
    tree = parser.parse(source.encode("utf-8"))
    results: list[FunctionMetrics] = []

    def collect(cur) -> None:
        if cur.type in FUNCTION_TYPES:
            results.append(_analyze_function(cur, source, filename))
        for child in cur.children:
            collect(child)

    collect(tree.root_node)
    return results


def analyze_file(path: Path, root: Path | None = None) -> list[FunctionMetrics]:
    source = path.read_text(encoding="utf-8", errors="replace")
    rel = str(path.relative_to(root)) if root else str(path)
    return analyze_source(source, rel, path=path)
