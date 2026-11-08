"""Call graph, CFG, and DFG from Python ASTs (in-memory IR for Task 6)."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GraphStats:
    kind: str
    nodes: int
    edges: int
    extra: dict = field(default_factory=dict)


def _functions(tree: ast.AST, filename: str) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    out: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    class C(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            out.append((f"{filename}:{node.name}", node))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            out.append((f"{filename}:{node.name}", node))
            self.generic_visit(node)

    C().visit(tree)
    return out


def count_ast(trees: dict[str, ast.AST]) -> GraphStats:
    nodes = 0
    edges = 0
    for tree in trees.values():
        for node in ast.walk(tree):
            nodes += 1
            edges += len(list(ast.iter_child_nodes(node)))
    return GraphStats("pure_ast", nodes, edges)


def build_cfg(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> GraphStats:
    nodes = 2  # entry, exit
    edges = 0
    stmts = list(fn.body)
    if not stmts:
        return GraphStats("cfg", 2, 1)

    def walk(body: list[ast.stmt]) -> None:
        nonlocal nodes, edges
        for stmt in body:
            nodes += 1
            edges += 1
            if isinstance(stmt, ast.If):
                walk(stmt.body)
                walk(stmt.orelse)
                edges += 2
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                walk(stmt.body)
                edges += 2
            elif isinstance(stmt, ast.Try):
                walk(stmt.body)
                for h in stmt.handlers:
                    walk(h.body)
                    edges += 1
                walk(stmt.orelse)
                walk(stmt.finalbody)
            elif isinstance(stmt, ast.Return):
                edges += 1

    walk(stmts)
    edges += 1
    return GraphStats("cfg", nodes, edges)


def build_dfg(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> GraphStats:
    defs: dict[str, int] = {}
    names: set[str] = set()
    edges = 0

    class V(ast.NodeVisitor):
        def visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            for arg in node.args.args:
                defs[arg.arg] = id(arg)
                names.add(arg.arg)
            for child in node.body:
                self.visit(child)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is fn:
                self.visit_function(node)
            # nested: skip inner as separate DFG

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is fn:
                self.visit_function(node)

        def visit_Name(self, node: ast.Name) -> None:
            names.add(node.id)
            nonlocal edges
            if isinstance(node.ctx, ast.Store):
                defs[node.id] = id(node)
            elif isinstance(node.ctx, ast.Load) and node.id in defs:
                edges += 1

    V().visit(fn)
    return GraphStats("dfg", len(names), edges)


def _imports(tree: ast.AST) -> dict[str, str]:
    """local name -> module file stem guess (db for `from db import get_user`)."""
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.split(".")[-1]
            for alias in node.names:
                mapping[alias.asname or alias.name] = mod
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mapping[alias.asname or alias.name.split(".")[0]] = alias.name.split(".")[0]
    return mapping


def _call_basename(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def build_call_graph(trees: dict[str, ast.AST]) -> GraphStats:
    defined: dict[str, str] = {}  # short name -> qual (last wins if collision)
    defined_qual: set[str] = set()
    file_of: dict[str, str] = {}
    for filename, tree in trees.items():
        stem = Path(filename).stem
        for qual, fn in _functions(tree, filename):
            defined[fn.name] = qual
            defined[f"{stem}.{fn.name}"] = qual
            defined_qual.add(qual)
            file_of[fn.name] = filename

    nodes: set[str] = set(defined_qual)
    edges = 0
    resolved = 0
    unresolved = 0
    cross_file = 0
    edge_list: list[tuple[str, str]] = []

    for filename, tree in trees.items():
        imports = _imports(tree)
        for qual, fn in _functions(tree, filename):
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                name = _call_basename(node)
                target = None
                if isinstance(node.func, ast.Name) and node.func.id in defined:
                    target = defined[node.func.id]
                elif name and name in defined:
                    target = defined[name]
                elif isinstance(node.func, ast.Name) and node.func.id in imports:
                    mod = imports[node.func.id]
                    key = f"{mod}.{name}" if name else None
                    if key and key in defined:
                        target = defined[key]
                if target:
                    edges += 1
                    resolved += 1
                    nodes.add(target)
                    edge_list.append((qual, target))
                    if Path(qual.split(":")[0]).name != Path(target.split(":")[0]).name:
                        cross_file += 1
                else:
                    unresolved += 1

    return GraphStats(
        "call_graph",
        len(nodes),
        edges,
        extra={
            "resolved_calls": resolved,
            "unresolved_calls": unresolved,
            "resolution_rate": round(resolved / (resolved + unresolved), 3)
            if (resolved + unresolved)
            else 0.0,
            "cross_file_edges": cross_file,
            "edges_sample": edge_list[:20],
        },
    )


def build_cfg_dfg_cg(trees: dict[str, ast.AST]) -> dict[str, GraphStats]:
    """Config B: Call Graph + CFG + DFG (no AST counts)."""
    cfg = GraphStats("cfg", 0, 0)
    dfg = GraphStats("dfg", 0, 0)
    for filename, tree in trees.items():
        for _, fn in _functions(tree, filename):
            c = build_cfg(fn)
            d = build_dfg(fn)
            cfg.nodes += c.nodes
            cfg.edges += c.edges
            dfg.nodes += d.nodes
            dfg.edges += d.edges
    return {"cfg": cfg, "dfg": dfg, "call_graph": build_call_graph(trees)}


def build_all_graphs(trees: dict[str, ast.AST]) -> dict[str, GraphStats]:
    graphs = build_cfg_dfg_cg(trees)
    graphs["pure_ast"] = count_ast(trees)
    return graphs


def parse_python_files(paths: list[Path], root: Path) -> dict[str, ast.AST]:
    trees: dict[str, ast.AST] = {}
    for path in paths:
        rel = str(path.relative_to(root))
        try:
            trees[rel] = ast.parse(
                path.read_text(encoding="utf-8", errors="replace"), filename=rel
            )
        except SyntaxError:
            continue
    return trees


def stats_to_dict(s: GraphStats) -> dict:
    d = {"kind": s.kind, "nodes": s.nodes, "edges": s.edges}
    d.update(s.extra)
    return d
