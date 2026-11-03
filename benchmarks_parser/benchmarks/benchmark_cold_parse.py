"""
Benchmark 1: Cold Parse Latency & Throughput
Measures initial full-file and multi-file project parsing performance:
  - Python: Standard `ast.parse` vs. `tree-sitter-python`
  - JavaScript: Babel `@babel/parser` & Acorn vs. `tree-sitter-javascript`
Metrics:
  - Latency (ms per file)
  - Throughput (lines per second & KB per second)
  - Speedup factor
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from parsers.native_ast.python_ast_parser import PythonNativeAstParser
from parsers.native_ast.js_ast_bridge import JavaScriptNativeAstBridge
from parsers.treesitter_cst.treesitter_python_parser import TreeSitterPythonParser
from parsers.treesitter_cst.treesitter_js_parser import TreeSitterJavaScriptParser


def run_cold_parse_benchmarks(iterations: int = 100) -> Dict[str, Any]:
    py_ast = PythonNativeAstParser()
    py_ts = TreeSitterPythonParser()
    js_bridge = JavaScriptNativeAstBridge()
    js_ts = TreeSitterJavaScriptParser()

    samples_dir = ROOT_DIR / "samples"
    results = {"python": {}, "javascript": {}, "multi_file_packages": {}}

    # --------------------------------------------------------------------------
    # 1. Python Corpora
    # --------------------------------------------------------------------------
    py_files = {
        "Small (~30 LOC)": samples_dir / "python" / "small_auth_utils.py",
        "Medium (~160 LOC)": samples_dir / "python" / "medium_db_service.py",
        "Large (~1,200 LOC)": samples_dir / "python" / "large_api_controller.py",
    }

    for label, path in py_files.items():
        code_str = path.read_text(encoding="utf-8")
        code_bytes = code_str.encode("utf-8")
        loc = len(code_str.splitlines())
        size_kb = len(code_bytes) / 1024

        # Native AST
        ast_times = []
        for _ in range(iterations):
            _, lat = py_ast.parse(code_str)
            ast_times.append(lat)
        avg_ast = sum(ast_times) / len(ast_times)

        # Tree-sitter CST
        ts_times = []
        for _ in range(iterations):
            _, lat = py_ts.parse(code_bytes)
            ts_times.append(lat)
        avg_ts = sum(ts_times) / len(ts_times)

        speedup = avg_ast / avg_ts if avg_ts > 0 else 1.0
        ts_throughput_lps = (loc / (avg_ts / 1000)) if avg_ts > 0 else 0

        results["python"][label] = {
            "file": path.name,
            "loc": loc,
            "size_kb": round(size_kb, 2),
            "native_ast_ms": round(avg_ast, 4),
            "treesitter_cst_ms": round(avg_ts, 4),
            "speedup_factor": round(speedup, 2),
            "treesitter_throughput_lines_sec": int(ts_throughput_lps)
        }

    # --------------------------------------------------------------------------
    # 2. JavaScript Corpora
    # --------------------------------------------------------------------------
    js_files = {
        "Small (~30 LOC)": samples_dir / "javascript" / "small_jwt_helper.js",
        "Medium (~250 LOC)": samples_dir / "javascript" / "medium_express_router.js",
        "Large (~1,200 LOC)": samples_dir / "javascript" / "large_app_bundle.js",
    }

    for label, path in js_files.items():
        code_str = path.read_text(encoding="utf-8")
        code_bytes = code_str.encode("utf-8")
        loc = len(code_str.splitlines())
        size_kb = len(code_bytes) / 1024

        # JS Node native (Babel & Acorn)
        node_res = js_bridge.benchmark_file(str(path), iterations=iterations)
        babel_ms = node_res["babel_avg_ms"]
        acorn_ms = node_res["acorn_avg_ms"]

        # Tree-sitter CST
        ts_times = []
        for _ in range(iterations):
            _, lat = js_ts.parse(code_bytes)
            ts_times.append(lat)
        avg_ts = sum(ts_times) / len(ts_times)

        speedup_vs_babel = babel_ms / avg_ts if avg_ts > 0 else 1.0
        speedup_vs_acorn = acorn_ms / avg_ts if avg_ts > 0 else 1.0
        ts_throughput_lps = (loc / (avg_ts / 1000)) if avg_ts > 0 else 0

        results["javascript"][label] = {
            "file": path.name,
            "loc": loc,
            "size_kb": round(size_kb, 2),
            "babel_ast_ms": babel_ms,
            "acorn_estree_ms": acorn_ms,
            "treesitter_cst_ms": round(avg_ts, 4),
            "speedup_vs_babel": round(speedup_vs_babel, 2),
            "speedup_vs_acorn": round(speedup_vs_acorn, 2),
            "treesitter_throughput_lines_sec": int(ts_throughput_lps)
        }

    # --------------------------------------------------------------------------
    # 3. Multi-File Project Mini-Packages
    # --------------------------------------------------------------------------
    # Python Multi-file
    py_pkg = samples_dir / "python" / "multi_file_project"
    py_pkg_files = list(py_pkg.glob("*.py"))
    total_py_loc = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in py_pkg_files)

    t0 = time.perf_counter()
    for _ in range(iterations):
        for f in py_pkg_files:
            _ = py_ast.parse(f.read_text(encoding="utf-8"))
    t1 = time.perf_counter()
    py_ast_pkg_ms = ((t1 - t0) * 1000) / iterations

    t0 = time.perf_counter()
    for _ in range(iterations):
        for f in py_pkg_files:
            _ = py_ts.parse(f.read_bytes())
    t1 = time.perf_counter()
    py_ts_pkg_ms = ((t1 - t0) * 1000) / iterations

    results["multi_file_packages"]["python_package"] = {
        "files_count": len(py_pkg_files),
        "total_loc": total_py_loc,
        "native_ast_batch_ms": round(py_ast_pkg_ms, 4),
        "treesitter_cst_batch_ms": round(py_ts_pkg_ms, 4),
        "speedup_factor": round(py_ast_pkg_ms / py_ts_pkg_ms if py_ts_pkg_ms > 0 else 1.0, 2)
    }

    # JavaScript Multi-file
    js_pkg = samples_dir / "javascript" / "multi_file_project"
    js_pkg_files = list(js_pkg.glob("*.js"))
    total_js_loc = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in js_pkg_files)

    t0 = time.perf_counter()
    for _ in range(iterations):
        for f in js_pkg_files:
            _ = js_ts.parse(f.read_bytes())
    t1 = time.perf_counter()
    js_ts_pkg_ms = ((t1 - t0) * 1000) / iterations

    results["multi_file_packages"]["javascript_package"] = {
        "files_count": len(js_pkg_files),
        "total_loc": total_js_loc,
        "treesitter_cst_batch_ms": round(js_ts_pkg_ms, 4),
    }

    return results


if __name__ == "__main__":
    import pprint
    res = run_cold_parse_benchmarks(iterations=50)
    pprint.pprint(res)
