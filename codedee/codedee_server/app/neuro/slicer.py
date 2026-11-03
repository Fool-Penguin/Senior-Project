"""
slicer.py - Concrete Syntax Tree (CST) Program Slicer for CodeDEE.

Performs Full Function / Method Extraction and Statement Boundary Slicing
for Python, JavaScript, and TypeScript, retaining complete semantic context
surrounding taint sources and sinks.
"""

from typing import Any, Dict, List, Optional, Tuple
import tree_sitter

from ..parser.cst_manager import CSTParserManager

FUNCTION_NODE_TYPES = {
    "python": {"function_definition", "decorated_definition"},
    "javascript": {
        "function_declaration",
        "function_expression",
        "method_definition",
        "arrow_function",
    },
    "typescript": {
        "function_declaration",
        "function_expression",
        "method_definition",
        "arrow_function",
    },
}


class ProgramSlicer:
    """
    Extracts full function / method slices or aligned statement slices for vulnerability sources and sinks.
    """

    def __init__(self) -> None:
        self.cst_manager = CSTParserManager.get_instance()

    def _extract_function_name(self, node: tree_sitter.Node, code: str) -> str:
        """Helper to extract clean function/method name from a CST node."""
        # 1. Direct identifier or property_identifier
        for child in node.children:
            if child.type in ("identifier", "property_identifier"):
                return code[child.start_byte : child.end_byte]

        # 2. Check field 'name'
        name_node = node.child_by_field_name("name")
        if name_node:
            return code[name_node.start_byte : name_node.end_byte]

        # 3. For decorated definition, inspect inner function_definition
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type == "function_definition":
                    return self._extract_function_name(child, code)

        return "anonymous"

    def find_enclosing_function(
        self,
        tree: tree_sitter.Tree,
        line_num: int,
        language: str,
        code: Optional[str] = None,
    ) -> Optional[Tuple[tree_sitter.Node, str]]:
        """
        Locate innermost or top enclosing function node around 1-based line_num.
        Supports Python decorated functions and JS/TS lexical bindings/exports.
        Returns (node, function_name).
        """
        target_row = max(0, line_num - 1)
        lang_key = language.lower()
        func_types = FUNCTION_NODE_TYPES.get(
            lang_key, {"function_definition", "function_declaration"}
        )

        matched_node: Optional[tree_sitter.Node] = None

        def visit(node: tree_sitter.Node):
            nonlocal matched_node
            if node.type in func_types:
                if node.start_point.row <= target_row <= node.end_point.row:
                    matched_node = node
            for child in node.children:
                visit(child)

        visit(tree.root_node)

        if matched_node is None:
            return None

        # Snap to enclosing outer definitions for complete context
        # Python: snap function_definition to decorated_definition if present
        if lang_key == "python":
            if matched_node.parent and matched_node.parent.type == "decorated_definition":
                matched_node = matched_node.parent

        # JavaScript / TypeScript: snap arrow_function or function_expression to variable_declarator/lexical_declaration/export_statement
        elif lang_key in ("javascript", "typescript"):
            if matched_node.type in ("arrow_function", "function_expression"):
                parent = matched_node.parent
                if parent and parent.type == "variable_declarator":
                    lexical = parent.parent
                    if lexical and lexical.type in ("lexical_declaration", "variable_declaration"):
                        if lexical.parent and lexical.parent.type == "export_statement":
                            matched_node = lexical.parent
                        else:
                            matched_node = lexical
            elif matched_node.type == "function_declaration":
                if matched_node.parent and matched_node.parent.type == "export_statement":
                    matched_node = matched_node.parent

        # Extract function name
        fn_name = "anonymous"
        if code:
            fn_name = self._extract_function_name(matched_node, code)
            # If still anonymous and node is a lexical/variable declaration or export, check declarator name
            if fn_name == "anonymous":
                for child in matched_node.children:
                    if child.type == "variable_declarator":
                        name_child = child.child_by_field_name("name")
                        if name_child:
                            fn_name = code[name_child.start_byte : name_child.end_byte]
                            break
                        for c in child.children:
                            if c.type == "identifier":
                                fn_name = code[c.start_byte : c.end_byte]
                                break
                    elif child.type == "export_statement":
                        fn_name = self._extract_function_name(child, code)
                        break
        else:
            # Fallback when code string is not provided
            for child in matched_node.children:
                if child.type in ("identifier", "property_identifier"):
                    fn_name = child.text.decode("utf-8", errors="replace")
                    break

        return (matched_node, fn_name)

    def slice_context(
        self,
        code: str,
        language: str,
        source_line: int,
        sink_line: int,
    ) -> Dict[str, Any]:
        """
        Perform Full Function / Method Extraction or Statement Boundary Slicing
        for source and sink lines.
        """
        tree = self.cst_manager.parse(code, language)
        src_func = self.find_enclosing_function(tree, source_line, language, code=code)
        snk_func = self.find_enclosing_function(tree, sink_line, language, code=code)

        lines = code.splitlines()

        # Case 1: Both belong to the same enclosing function
        if src_func and snk_func and src_func[0] == snk_func[0]:
            func_node, func_name = src_func
            start_row = func_node.start_point.row
            end_row = func_node.end_point.row
            slice_code = "\n".join(lines[start_row : end_row + 1])
            return {
                "slice_type": "single_function",
                "function_names": [func_name],
                "slice_code": slice_code,
                "start_line": start_row + 1,
                "end_line": end_row + 1,
            }

        # Case 2: Belong to distinct enclosing functions (inter-procedural flow)
        if src_func and snk_func and src_func[0] != snk_func[0]:
            src_node, src_name = src_func
            snk_node, snk_name = snk_func

            src_code = "\n".join(lines[src_node.start_point.row : src_node.end_point.row + 1])
            snk_code = "\n".join(lines[snk_node.start_point.row : snk_node.end_point.row + 1])
            combined_slice = (
                f"// Source Function: {src_name} (lines {src_node.start_point.row+1}-{src_node.end_point.row+1})\n"
                f"{src_code}\n\n"
                f"// Sink Function: {snk_name} (lines {snk_node.start_point.row+1}-{snk_node.end_point.row+1})\n"
                f"{snk_code}"
            )
            return {
                "slice_type": "inter_procedural_functions",
                "function_names": [src_name, snk_name],
                "slice_code": combined_slice,
                "start_line": min(src_node.start_point.row, snk_node.start_point.row) + 1,
                "end_line": max(src_node.end_point.row, snk_node.end_point.row) + 1,
            }

        # Case 3: Only source or only sink has an enclosing function
        single_func = snk_func or src_func
        if single_func:
            func_node, func_name = single_func
            start_row = func_node.start_point.row
            end_row = func_node.end_point.row
            slice_code = "\n".join(lines[start_row : end_row + 1])
            return {
                "slice_type": "enclosing_function",
                "function_names": [func_name],
                "slice_code": slice_code,
                "start_line": start_row + 1,
                "end_line": end_row + 1,
            }

        # Case 4: File is a top-level script without enclosing function declarations
        if len(lines) <= 60:
            return {
                "slice_type": "full_snippet",
                "function_names": ["global_scope"],
                "slice_code": code,
                "start_line": 1,
                "end_line": len(lines),
            }

        # Statement boundary alignment for larger scripts (>60 lines)
        # Find top-level statement nodes overlapping [source_line, sink_line]
        named_children = [c for c in tree.root_node.children if c.is_named]
        import_lines: List[str] = []
        target_statements: List[tree_sitter.Node] = []

        min_row = min(source_line - 1, sink_line - 1)
        max_row = max(source_line - 1, sink_line - 1)

        for child in named_children:
            if "import" in child.type or child.type == "require_call":
                import_lines.extend(lines[child.start_point.row : child.end_point.row + 1])
            elif not (child.end_point.row < min_row or child.start_point.row > max_row):
                target_statements.append(child)

        if not target_statements:
            # Fallback to lines surrounding min_row and max_row
            start_r = max(0, min_row - 3)
            end_r = min(len(lines) - 1, max_row + 3)
            slice_body = "\n".join(lines[start_r : end_r + 1])
        else:
            # Expand window by 3 statements before and 3 statements after
            idx_start = max(0, named_children.index(target_statements[0]) - 3)
            idx_end = min(len(named_children) - 1, named_children.index(target_statements[-1]) + 3)
            start_r = named_children[idx_start].start_point.row
            end_r = named_children[idx_end].end_point.row
            slice_body = "\n".join(lines[start_r : end_r + 1])

        combined = ""
        if import_lines:
            combined = "\n".join(import_lines) + "\n\n// --- Context Window ---\n"
        combined += slice_body

        return {
            "slice_type": "statement_boundary_slice",
            "function_names": ["global_scope"],
            "slice_code": combined,
            "start_line": start_r + 1,
            "end_line": end_r + 1,
        }
