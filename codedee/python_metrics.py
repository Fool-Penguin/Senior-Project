"""Function-level maintainability metrics from the Python AST.

Cyclomatic complexity follows McCabe (decision points).
Cognitive complexity follows Campbell / Sonar (nesting-aware).
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path

# Align with the team's earlier Sonar-style gates (proposal thresholds).
THRESHOLDS = {
    "cyclomatic": {"moderate": 10, "high": 15},
    "cognitive": {"moderate": 8, "high": 15},
    "loc": {"moderate": 50, "high": 100},
    "nesting": {"moderate": 3, "high": 4},
    "params": {"moderate": 4, "high": 5},
}


@dataclass
class FunctionMetrics:
    file: str
    function: str
    line: int
    end_line: int
    loc: int
    sloc: int
    params: int
    cyclomatic: int
    cognitive: int
    max_nesting: int
    findings: list[str]


def _sloc(node: ast.AST, source: str) -> tuple[int, int]:
    end = getattr(node, "end_lineno", None) or node.lineno
    start = node.lineno
    loc = end - start + 1
    lines = source.splitlines()[start - 1 : end]
    sloc = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    return loc, sloc


class _Cyclomatic(ast.NodeVisitor):
    def __init__(self) -> None:
        self.score = 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_If(self, node: ast.If) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.score += 1
        self.score += len(node.ifs)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.score += max(len(node.values) - 1, 0)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.score += len(node.cases)
        self.generic_visit(node)


class _Cognitive(ast.NodeVisitor):
    """Nesting-aware cognitive complexity (Campbell-style)."""

    def __init__(self) -> None:
        self.score = 0
        self.nesting = 0
        self.max_nesting = 0

    def _bump_nest(self) -> None:
        self.nesting += 1
        self.max_nesting = max(self.max_nesting, self.nesting)

    def visit_If(self, node: ast.If) -> None:
        self.score += 1 + self.nesting
        self._bump_nest()
        for child in node.body:
            self.visit(child)
        self.nesting -= 1
        orelse = node.orelse
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            # elif: +1 at this nesting, not an extra nested if
            self.visit_If(orelse[0])
        elif orelse:
            self.score += 1
            for child in orelse:
                self.visit(child)

    def visit_For(self, node: ast.For) -> None:
        self.score += 1 + self.nesting
        self._bump_nest()
        self.generic_visit(node)
        self.nesting -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.score += 1 + self.nesting
        self._bump_nest()
        self.generic_visit(node)
        self.nesting -= 1

    def visit_While(self, node: ast.While) -> None:
        self.score += 1 + self.nesting
        self._bump_nest()
        self.generic_visit(node)
        self.nesting -= 1

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.score += 1 + self.nesting
        self._bump_nest()
        self.generic_visit(node)
        self.nesting -= 1

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.score += 1 + self.nesting
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.score += 1 + self.nesting
        for if_ in node.ifs:
            self.score += 1 + self.nesting
            self.visit(if_)
        self.visit(node.iter)
        self.visit(node.target)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.score += 1 + self.nesting
        self._bump_nest()
        self.generic_visit(node)
        self.nesting -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return  # nested functions are scored separately

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


def _param_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    args = node.args
    return (
        len(args.posonlyargs)
        + len(args.args)
        + len(args.kwonlyargs)
        + (1 if args.vararg else 0)
        + (1 if args.kwarg else 0)
    )


def _findings(m: FunctionMetrics) -> list[str]:
    out = []
    if m.cyclomatic >= THRESHOLDS["cyclomatic"]["high"]:
        out.append(f"cyclomatic {m.cyclomatic} >= {THRESHOLDS['cyclomatic']['high']} (high)")
    elif m.cyclomatic >= THRESHOLDS["cyclomatic"]["moderate"]:
        out.append(f"cyclomatic {m.cyclomatic} >= {THRESHOLDS['cyclomatic']['moderate']} (moderate)")
    if m.cognitive >= THRESHOLDS["cognitive"]["high"]:
        out.append(f"cognitive {m.cognitive} >= {THRESHOLDS['cognitive']['high']} (high)")
    elif m.cognitive >= THRESHOLDS["cognitive"]["moderate"]:
        out.append(f"cognitive {m.cognitive} >= {THRESHOLDS['cognitive']['moderate']} (moderate)")
    if m.loc >= THRESHOLDS["loc"]["high"]:
        out.append(f"loc {m.loc} >= {THRESHOLDS['loc']['high']} (god function)")
    elif m.loc >= THRESHOLDS["loc"]["moderate"]:
        out.append(f"loc {m.loc} >= {THRESHOLDS['loc']['moderate']} (long method)")
    if m.max_nesting >= THRESHOLDS["nesting"]["high"]:
        out.append(f"nesting {m.max_nesting} >= {THRESHOLDS['nesting']['high']}")
    elif m.max_nesting >= THRESHOLDS["nesting"]["moderate"]:
        out.append(f"nesting {m.max_nesting} >= {THRESHOLDS['nesting']['moderate']}")
    if m.params >= THRESHOLDS["params"]["high"]:
        out.append(f"params {m.params} >= {THRESHOLDS['params']['high']}")
    return out


def analyze_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source: str,
    filename: str,
) -> FunctionMetrics:
    loc, sloc = _sloc(node, source)
    cc = _Cyclomatic()
    for child in node.body:
        cc.visit(child)
    cog = _Cognitive()
    for child in node.body:
        cog.visit(child)
    m = FunctionMetrics(
        file=filename,
        function=node.name,
        line=node.lineno,
        end_line=getattr(node, "end_lineno", None) or node.lineno,
        loc=loc,
        sloc=sloc,
        params=_param_count(node),
        cyclomatic=cc.score,
        cognitive=cog.score,
        max_nesting=cog.max_nesting,
        findings=[],
    )
    m.findings = _findings(m)
    return m


def analyze_source(source: str, filename: str) -> list[FunctionMetrics]:
    tree = ast.parse(source, filename=filename)
    results: list[FunctionMetrics] = []

    class Collector(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            results.append(analyze_function(node, source, filename))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            results.append(analyze_function(node, source, filename))
            self.generic_visit(node)

    Collector().visit(tree)
    return results


def analyze_file(path: Path, root: Path | None = None) -> list[FunctionMetrics]:
    source = path.read_text(encoding="utf-8", errors="replace")
    rel = str(path.relative_to(root)) if root else str(path)
    return analyze_source(source, rel)


def metrics_to_dict(m: FunctionMetrics) -> dict:
    return asdict(m)
