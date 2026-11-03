"""
Native Python AST Parser Engine
Wraps Python's built-in `ast` module (CPython C-accelerated parser).
Measures:
  - Cold parse latency
  - Full file re-parse latency
  - Comment preservation capability (AST discard test)
  - Error recovery capability (SyntaxError fatal abort)
"""

import ast
import time
from typing import Dict, Any, Tuple, Optional


class PythonNativeAstParser:
    """Standard Language-Native AST Parser for Python."""

    def __init__(self):
        self.engine_name = "Python Native AST (ast.parse)"

    def parse(self, code_str: str) -> Tuple[Optional[ast.AST], float]:
        """Parses python source code string into an AST, measuring latency in milliseconds."""
        t0 = time.perf_counter()
        tree = ast.parse(code_str)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000
        return tree, latency_ms

    def reparse_full(self, modified_code_str: str) -> Tuple[Optional[ast.AST], float]:
        """Simulates how standard ASTs must re-parse from scratch upon any buffer edit."""
        return self.parse(modified_code_str)

    def extract_comments_count(self, tree: ast.AST) -> int:
        """
        Demonstrates that Standard AST strips out comments and trivia.
        Only docstrings stored as Expr(Constant(str)) survive; inline `#` comments are discarded.
        """
        comment_nodes = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
                val = str(node.value.value)
                if val.strip().startswith("#"):
                    comment_nodes += 1
        return comment_nodes

    def test_error_recovery(self, broken_code_str: str) -> Dict[str, Any]:
        """Tests whether parser can recover or aborts fatally with SyntaxError."""
        try:
            _ = ast.parse(broken_code_str)
            return {"fatal_abort": False, "recovered": True, "error_type": None}
        except SyntaxError as e:
            return {
                "fatal_abort": True,
                "recovered": False,
                "error_type": "SyntaxError",
                "message": str(e.msg),
                "lineno": e.lineno,
                "offset": e.offset,
            }


def inspect_ast_file(file_path: Path, parser: PythonNativeAstParser):
    code = file_path.read_text(encoding="utf-8")
    tree, lat = parser.parse(code)

    print("=" * 80)
    print(f"Native Python AST: {file_path.name} (Parsed in {lat:.3f} ms)")
    print("=" * 80)
    print(f"Top-level AST Body Nodes ({len(tree.body)} nodes):")
    for idx, node in enumerate(tree.body[:15]):
        print(f"  [{idx}] {type(node).__name__} (lines {getattr(node, 'lineno', '?')}-{getattr(node, 'end_lineno', '?')})")

    print("\n--- PURE AST DUMP (ast.dump with indent=2) ---")
    dump_lines = ast.dump(tree, indent=2).splitlines()
    for l in dump_lines[:25]:
        print("  " + l)
    if len(dump_lines) > 25:
        print(f"  ... ({len(dump_lines) - 25} more AST dump lines)")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    target_str = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent.parent.parent / "samples/python/small_auth_utils.py")
    target_path = Path(target_str)

    if not target_path.exists():
        print(f"[Error] Target path not found: {target_path}")
        sys.exit(1)

    parser = PythonNativeAstParser()

    if target_path.is_dir():
        py_files = sorted(list(target_path.glob("*.py")))
        print("\n" + "#" * 80)
        print(f"BATCH DIRECTORY AST SCAN: {target_path.resolve()} ({len(py_files)} Python files)")
        print("#" * 80)
        for f in py_files:
            inspect_ast_file(f, parser)
            print("\n")
    else:
        inspect_ast_file(target_path, parser)
