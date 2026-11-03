"""
Visualizer Tool: Dual View (Original Code + Pure Syntax Tree Output)
Demonstrates Tree-sitter CST and Standard AST representations,
and explains how the pure tree is used to construct security graphs (CFG / DFG / Taint Graph).

Usage:
  python benchmarks_parser/visualize_tree.py [path_to_source_file] [max_depth]
"""

import ast
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from parsers.native_ast.python_ast_parser import PythonNativeAstParser
from parsers.treesitter_cst.treesitter_python_parser import TreeSitterPythonParser
from parsers.treesitter_cst.treesitter_js_parser import TreeSitterJavaScriptParser


def format_code_with_line_numbers(code_str: str) -> str:
    lines = code_str.splitlines()
    formatted = []
    for idx, line in enumerate(lines, 1):
        formatted.append(f"  {idx:>3} | {line}")
    return "\n".join(formatted)


def render_indented_cst(node, code_bytes: bytes, depth: int = 0, max_depth: int = 4, field_name: str = None) -> list:
    lines = []
    indent = "    " + "  " * depth
    prefix = f"{field_name}: " if field_name else ""
    
    # Extract short slice
    text = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip().replace("\n", " ")
    if len(text) > 30:
        text = text[:27] + "..."
    
    is_named = node.is_named
    type_str = node.type if is_named else f'"{node.type}"'
    lines.append(f"{indent}({prefix}{type_str} [{node.start_byte}:{node.end_byte}] \"{text}\"")

    if depth < max_depth:
        # Check named and unnamed children with field names
        for child in node.children:
            child_field = None
            # Find field name if applicable
            for i in range(node.child_count):
                if node.child(i) == child:
                    child_field = node.field_name_for_child(i)
                    break
            lines.extend(render_indented_cst(child, code_bytes, depth + 1, max_depth, child_field))

    return lines


def inspect_file(target_file: Path, max_depth: int = 3):
    code_bytes = target_file.read_bytes()
    code_str = code_bytes.decode("utf-8", errors="replace")
    is_python = target_file.suffix == ".py"

    print("=" * 80)
    print("CodeDEE Inspector: Original Code & Pure Syntax Tree Dual View")
    print(f"Target File: {target_file.name} ({len(code_str.splitlines())} lines, {len(code_bytes)} bytes, {'Python' if is_python else 'JavaScript'})")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 1. ORIGINAL SOURCE CODE
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f"[1] ORIGINAL SOURCE CODE: {target_file.name}")
    print("=" * 80)
    print(format_code_with_line_numbers(code_str))

    # --------------------------------------------------------------------------
    # 2. PURE TREE-SITTER CST OUTPUT
    # --------------------------------------------------------------------------
    if is_python:
        ts_parser = TreeSitterPythonParser()
    else:
        ts_parser = TreeSitterJavaScriptParser()

    cst_tree, cst_lat = ts_parser.parse(code_bytes)

    print("\n" + "=" * 80)
    print(f"[2] PURE TREE-SITTER CST OUTPUT (Parsed in {cst_lat:.3f} ms)")
    print("=" * 80)
    print(f"Root Node: <{cst_tree.root_node.type}> [{cst_tree.root_node.start_byte}:{cst_tree.root_node.end_byte}]")
    
    print("\n--- Canonical S-Expression (Pure Grammar Tree) ---")
    sexp_str = str(cst_tree.root_node)
    if len(sexp_str) > 300:
        print(sexp_str[:300] + "\n... (truncated S-expression)")
    else:
        print(sexp_str)

    print(f"\n--- Indented Pure CST Hierarchy (Depth <= {max_depth}) ---")
    tree_lines = render_indented_cst(cst_tree.root_node, code_bytes, depth=0, max_depth=max_depth)
    for line in tree_lines[:45]:
        print(line)
    if len(tree_lines) > 45:
        print(f"    ... ({len(tree_lines) - 45} deeper sub-nodes)")

    # --------------------------------------------------------------------------
    # 3. STANDARD NATIVE AST OUTPUT (COMPARISON)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[3] STANDARD NATIVE AST OUTPUT (Notice comments & whitespace stripped)")
    print("=" * 80)
    if is_python:
        ast_parser = PythonNativeAstParser()
        native_ast, ast_lat = ast_parser.parse(code_str)
        ast_dump_str = ast.dump(native_ast, indent=2)
        lines = ast_dump_str.splitlines()
        for l in lines[:30]:
            print("  " + l)
        if len(lines) > 30:
            print(f"  ... ({len(lines) - 30} more AST lines)")
    else:
        print("  (JavaScript ESTree AST output generated via Acorn/Babel)")


def main():
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1])
    else:
        target_path = ROOT_DIR / "samples/python/small_auth_utils.py"

    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    if not target_path.exists():
        print(f"[Error] Target not found: {target_path}")
        sys.exit(1)

    if target_path.is_dir():
        files = sorted(list(target_path.glob("*.py")) + list(target_path.glob("*.js")))
        if not files:
            print(f"[Warning] No .py or .js files found in directory: {target_path}")
            sys.exit(0)
        print(f"Discovered {len(files)} files in directory: {target_path}")
        for idx, f in enumerate(files, 1):
            print(f"\n{'#' * 80}")
            print(f"File [{idx}/{len(files)}]: {f.name}")
            print(f"{'#' * 80}")
            inspect_file(f, max_depth=max_depth)
    else:
        inspect_file(target_path, max_depth=max_depth)


if __name__ == "__main__":
    main()
