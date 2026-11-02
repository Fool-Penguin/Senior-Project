"""Walk a tree of Python files and emit maintainability metrics + optional graphs."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from codedee.js_metrics import analyze_file as analyze_js_file, is_js_source
from codedee.js_metrics import JsMetricsUnavailable
from codedee.python_graphs import build_all_graphs, parse_python_files, stats_to_dict
from codedee.python_metrics import FunctionMetrics, analyze_file as analyze_py_file, metrics_to_dict

SKIP_DIRS = {
    ".git",
    ".hg",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    "dist",
    "build",
    ".mypy_cache",
    "Test_dataset",
    "commit_diff_sample",
}


def iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if root.is_file() and root.suffix == ".py":
        return [root]
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def iter_js_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if root.is_file() and is_js_source(root):
        return [root]
    for path in root.rglob("*"):
        if not path.is_file() or not is_js_source(path):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def analyze_source_file(path: Path, root: Path) -> list[FunctionMetrics]:
    if path.suffix == ".py":
        return analyze_py_file(path, root=root)
    if is_js_source(path):
        return analyze_js_file(path, root=root)
    return []


def scan_maintainability(root: Path) -> dict:
    root = root.resolve()
    t0 = time.perf_counter()
    files = iter_python_files(root) + iter_js_files(root)
    functions: list[FunctionMetrics] = []
    errors: list[dict] = []
    for path in files:
        try:
            functions.extend(analyze_source_file(path, root if root.is_dir() else path.parent))
        except SyntaxError as exc:
            errors.append({"file": str(path), "error": str(exc)})
        except JsMetricsUnavailable as exc:
            errors.append({"file": str(path), "error": str(exc)})
            break
    elapsed = time.perf_counter() - t0
    with_findings = [m for m in functions if m.findings]
    return {
        "engine": "codedee-maintainability",
        "root": str(root),
        "files_scanned": len(files),
        "functions": len(functions),
        "functions_with_findings": len(with_findings),
        "scan_seconds": round(elapsed, 4),
        "errors": errors,
        "records": [metrics_to_dict(m) for m in functions],
    }


def scan_graphs(root: Path) -> dict:
    import tracemalloc

    root = root.resolve()
    files = iter_python_files(root)
    tracemalloc.start()
    t0 = time.perf_counter()
    trees = parse_python_files(files, root if root.is_dir() else root.parent)
    parse_ms = (time.perf_counter() - t0) * 1000
    _, parse_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    t1 = time.perf_counter()
    graphs = build_all_graphs(trees)
    build_ms = (time.perf_counter() - t1) * 1000
    _, graph_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "engine": "codedee-graphs",
        "root": str(root),
        "files": list(trees),
        "parse_latency_ms": round(parse_ms, 3),
        "graph_latency_ms": round(build_ms, 3),
        "parse_peak_bytes": parse_peak,
        "graph_peak_bytes": graph_peak,
        "graphs": {k: stats_to_dict(v) for k, v in graphs.items()},
    }


def write_csv(records: list[dict], path: Path) -> None:
    if not records:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = [
        "file",
        "function",
        "line",
        "end_line",
        "loc",
        "sloc",
        "params",
        "cyclomatic",
        "cognitive",
        "max_nesting",
        "findings",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in records:
            out = dict(row)
            out["findings"] = "; ".join(row.get("findings") or [])
            w.writerow(out)


def dump_json(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
