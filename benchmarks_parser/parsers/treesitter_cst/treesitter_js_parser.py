"""
Tree-sitter Concrete Syntax Tree (CST) Parser for JavaScript
Uses tree-sitter-javascript grammar.
"""

import time
from typing import Tuple, List, Dict, Any
from tree_sitter import Language, Parser, Tree, Node
import tree_sitter_javascript as tsjavascript

JS_LANGUAGE = Language(tsjavascript.language())


class TreeSitterJavaScriptParser:
    """Tree-sitter CST Parser for JavaScript source files."""

    def __init__(self):
        self.parser = Parser(JS_LANGUAGE)
        self.language = JS_LANGUAGE

    def parse(self, code_bytes: bytes, old_tree: Tree = None) -> Tuple[Tree, float]:
        """Parses JavaScript bytes into a Concrete Syntax Tree."""
        t0 = time.perf_counter()
        if old_tree is not None:
            tree = self.parser.parse(code_bytes, old_tree)
        else:
            tree = self.parser.parse(code_bytes)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000
        return tree, latency_ms

    def extract_comment_nodes(self, tree: Tree) -> List[Node]:
        """Extracts comment nodes from CST."""
        comments = []

        def traverse(node: Node):
            if node.type == "comment":
                comments.append(node)
            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return comments

    def check_error_nodes(self, tree: Tree) -> Dict[str, Any]:
        """Inspects for error recovery."""
        error_nodes = []

        def traverse(node: Node):
            if node.type == "ERROR" or node.is_missing:
                error_nodes.append({
                    "type": node.type,
                    "is_missing": node.is_missing,
                    "byte_range": (node.start_byte, node.end_byte)
                })
            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return {
            "has_error_nodes": len(error_nodes) > 0,
            "error_nodes_count": len(error_nodes),
            "recovers_and_continues": True,
        }


def inspect_javascript_file(file_path: Path, parser: TreeSitterJavaScriptParser):
    code_bytes = file_path.read_bytes()
    tree, lat = parser.parse(code_bytes)

    print("=" * 80)
    print(f"Tree-sitter JavaScript CST: {file_path.name} ({len(code_bytes)} bytes, parsed in {lat:.3f} ms)")
    print("=" * 80)

    # 1. Root & S-Expression (Pure Tree)
    print("\n--- [1] PURE S-EXPRESSION TREE ---")
    sexp_str = str(tree.root_node)
    if len(sexp_str) > 400:
        print(sexp_str[:400] + " ... (truncated S-expression)")
    else:
        print(sexp_str)

    # 2. Top-level CST structure
    print(f"\n--- [2] PURE CST STRUCTURE (Root: <{tree.root_node.type}> [{tree.root_node.start_byte}:{tree.root_node.end_byte}]) ---")
    for idx, child in enumerate(tree.root_node.children[:15]):
        snippet = code_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace").strip().splitlines()[0][:55]
        print(f"  +-- [{idx}] {child.type:<24} bytes: {child.start_byte:>4}-{child.end_byte:<4} | line: {child.start_point[0]+1:<3} -> {snippet}")
    if len(tree.root_node.children) > 15:
        print(f"      ... ({len(tree.root_node.children) - 15} more nodes)")

    # 3. Comment retention
    comments = parser.extract_comment_nodes(tree)
    print(f"\n--- [3] PRESERVED COMMENTS (TRIVIA): {len(comments)} comments retained ---")
    for c in comments[:3]:
        cmt_text = code_bytes[c.start_byte:c.end_byte].decode("utf-8", errors="replace").strip()
        print(f"  * line {c.start_point[0]+1}: {cmt_text[:60]}")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    target_str = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent.parent.parent / "samples/javascript/small_jwt_helper.js")
    target_path = Path(target_str)

    if not target_path.exists():
        print(f"[Error] Target path not found: {target_path}")
        sys.exit(1)

    parser = TreeSitterJavaScriptParser()

    if target_path.is_dir():
        js_files = sorted(list(target_path.glob("*.js")))
        print("\n" + "#" * 80)
        print(f"BATCH DIRECTORY SCAN: {target_path.resolve()} ({len(js_files)} JavaScript files)")
        print("#" * 80)
        for f in js_files:
            inspect_javascript_file(f, parser)
            print("\n")
    else:
        inspect_javascript_file(target_path, parser)
