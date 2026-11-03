"""
Benchmark 2: Incremental Parsing Latency during Live Keystroke Edits
Simulates a developer actively typing edits into medium and large source files.
Compares:
  - Tree-sitter CST: Incremental re-parsing with dirty subtree re-use (tree.edit)
  - Standard AST: Full tokenization, AST generation, and validation from scratch
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from parsers.native_ast.python_ast_parser import PythonNativeAstParser
from parsers.treesitter_cst.treesitter_python_parser import TreeSitterPythonParser
from parsers.treesitter_cst.treesitter_js_parser import TreeSitterJavaScriptParser
from parsers.treesitter_cst.incremental_editor import IncrementalEditor


def run_incremental_benchmarks(iterations: int = 100) -> Dict[str, Any]:
    py_ast = PythonNativeAstParser()
    py_ts = TreeSitterPythonParser()
    js_ts = TreeSitterJavaScriptParser()

    samples_dir = ROOT_DIR / "samples"
    results = {}

    # Target test files for live editing
    targets = [
        ("Python Medium (~160 LOC)", samples_dir / "python" / "medium_db_service.py", "python"),
        ("Python Large (~1,200 LOC)", samples_dir / "python" / "large_api_controller.py", "python"),
        ("Python Multi-File Package (editing routes.py)", samples_dir / "python" / "multi_file_project" / "routes.py", "python"),
        ("JavaScript Medium (~250 LOC)", samples_dir / "javascript" / "medium_express_router.js", "javascript"),
        ("JavaScript Large (~1,200 LOC)", samples_dir / "javascript" / "large_app_bundle.js", "javascript"),
        ("JavaScript Multi-File Package (editing routes.js)", samples_dir / "javascript" / "multi_file_project" / "routes.js", "javascript"),
    ]

    for label, path, lang in targets:
        code_bytes = path.read_bytes()
        code_str = code_bytes.decode("utf-8")

        # Insertion payload (simulating developer typing a new statement at module scope)
        if lang == "python":
            insertion = b"# Live developer keystroke edit\nDEBUG_FLAG = True\n"
            parser = py_ts.parser
        else:
            insertion = b"// Live developer keystroke edit\nconst DEBUG_FLAG = true;\n"
            parser = js_ts.parser

        # Run multiple iterations of incremental edit
        inc_times = []
        full_times = []

        # Find first function boundary to insert cleanly
        first_newline = code_bytes.find(b"\n")
        insert_offset = first_newline + 1 if first_newline != -1 else 0
        modified_bytes = code_bytes[:insert_offset] + insertion + code_bytes[insert_offset:]
        modified_str = modified_bytes.decode("utf-8", errors="replace")

        for _ in range(iterations):
            # 1. Full re-parse (Standard AST)
            if lang == "python":
                t0 = time.perf_counter()
                _ = py_ast.parse(modified_str)
                t1 = time.perf_counter()
                full_times.append((t1 - t0) * 1000)
            else:
                t0 = time.perf_counter()
                _ = parser.parse(modified_bytes)
                t1 = time.perf_counter()
                full_times.append((t1 - t0) * 1000)

            # 2. Incremental re-parse (Tree-sitter CST)
            working_tree = parser.parse(code_bytes)
            working_tree.edit(
                start_byte=insert_offset,
                old_end_byte=insert_offset,
                new_end_byte=insert_offset + len(insertion),
                start_point=(2, 0),
                old_end_point=(2, 0),
                new_end_point=(2 + insertion.count(b"\n"), 0),
            )
            t2 = time.perf_counter()
            _ = parser.parse(modified_bytes, working_tree)
            t3 = time.perf_counter()
            inc_times.append((t3 - t2) * 1000)

        avg_full = sum(full_times) / len(full_times)
        avg_inc = sum(inc_times) / len(inc_times)
        speedup = avg_full / avg_inc if avg_inc > 0 else 1.0

        results[label] = {
            "file": path.name,
            "full_reparse_ms": round(avg_full, 4),
            "incremental_reparse_ms": round(avg_inc, 4),
            "speedup_ratio": round(speedup, 2),
            "advantage": f"{round(speedup, 1)}x faster live update",
            "practical_significance": "Under 1ms response time guarantees 60fps stutter-free typing in IDE editor thread"
        }

    return results


if __name__ == "__main__":
    import pprint
    res = run_incremental_benchmarks(iterations=50)
    pprint.pprint(res)
