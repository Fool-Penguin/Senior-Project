"""
engine.py - ISO/IEC 25010 Maintainability Engine (Calculating Exactly 8 Metrics).

Calculates strictly and exclusively 8 ISO/IEC 25010 metrics:
Function-level:
  1. Cyclomatic Complexity (CC)
  2. Cognitive Complexity
  3. Parameter Count
  4. Function SLOC
File-level:
  5. File SLOC
  6. Module Coupling (Ce / Ca)
  7. Duplicated Blocks
  8. Comment Density

Strictly excludes: SQALE, LCOM4, DIT, NOM, Raw LOC, and Nesting Depth.
"""

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import tree_sitter

from ..models.contracts import MaintainabilityMetrics
from ..parser.cst_manager import CSTParserManager, LanguageType


@dataclass
class FunctionMetrics:
    name: str
    start_line: int
    end_line: int
    cyclomatic_complexity: int
    cognitive_complexity: int
    parameter_count: int
    function_sloc: int


@dataclass
class FileMetrics:
    file_path: str
    file_sloc: int
    module_coupling_ce: int
    module_coupling_ca: int
    instability: float
    duplicated_blocks: int
    comment_density: float
    function_metrics: List[FunctionMetrics]


class MaintainabilityEngine:
    """
    ISO/IEC 25010 Maintainability Engine.
    Computes exactly the 8 authorized metrics with zero forbidden metrics.
    """

    def __init__(self) -> None:
        self.cst_manager = CSTParserManager.get_instance()

    def analyze_code(
        self,
        code: str,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
        ca_coupling: int = 0,
    ) -> MaintainabilityMetrics:
        """
        Analyze code string and compute aggregate MaintainabilityMetrics (8 metrics).
        """
        lang = language or (
            self.cst_manager.detect_language(file_path, code)
            if file_path
            else LanguageType.PYTHON.value
        )
        norm_lang = self.cst_manager.normalize_language(lang)
        tree = self.cst_manager.parse(code, norm_lang)
        source_bytes = code.encode("utf-8")
        lines = code.splitlines()

        # Identify comment lines
        comment_line_set = self._extract_comment_lines(tree, lines, norm_lang)
        file_sloc = self.compute_file_sloc(lines, comment_line_set)
        comment_density = self.compute_comment_density(len(comment_line_set), file_sloc)

        # File-level module coupling
        ce, ca, _ = self.compute_module_coupling(tree, norm_lang, ca_coupling)

        # Duplicated blocks
        dup_blocks = self.compute_duplicated_blocks(tree, lines, norm_lang)

        # Function-level analysis
        func_nodes = self.cst_manager.get_functions(tree, norm_lang)
        func_reports: List[FunctionMetrics] = []

        for fn in func_nodes:
            f_metrics = self.analyze_function(fn, source_bytes, lines, comment_line_set, norm_lang)
            func_reports.append(f_metrics)

        # Aggregate function-level metrics (take max or representative values)
        if func_reports:
            agg_cc = max(f.cyclomatic_complexity for f in func_reports)
            agg_cog = max(f.cognitive_complexity for f in func_reports)
            agg_params = max(f.parameter_count for f in func_reports)
            agg_func_sloc = max(f.function_sloc for f in func_reports)
        else:
            # Standalone script without function declarations
            agg_cc = 1
            agg_cog = 0
            agg_params = 0
            agg_func_sloc = file_sloc

        return MaintainabilityMetrics(
            cyclomatic_complexity=agg_cc,
            cognitive_complexity=agg_cog,
            parameter_count=agg_params,
            function_sloc=agg_func_sloc,
            file_sloc=file_sloc,
            module_coupling_ce=ce,
            module_coupling_ca=ca,
            duplicated_blocks=dup_blocks,
            comment_density=comment_density,
        )

    def analyze_file(
        self,
        file_path: str,
        ca_coupling: int = 0,
    ) -> MaintainabilityMetrics:
        """
        Read file from disk and compute MaintainabilityMetrics.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()
        return self.analyze_code(code, file_path=file_path, ca_coupling=ca_coupling)

    def analyze_function(
        self,
        fn_node: tree_sitter.Node,
        source_bytes: bytes,
        source_lines: List[str],
        comment_line_set: Set[int],
        language: str,
    ) -> FunctionMetrics:
        """
        Calculate the 4 function-level metrics for a specific function node.
        """
        name_node = fn_node.child_by_field_name("name")
        fn_name = (
            self.cst_manager.get_node_text(name_node, source_bytes)
            if name_node
            else f"anonymous_L{fn_node.start_point.row + 1}"
        )

        cc = self.compute_cyclomatic_complexity(fn_node, language)
        cog = self.compute_cognitive_complexity(fn_node, language)
        params = self.compute_parameter_count(fn_node, language)
        f_sloc = self.compute_function_sloc(fn_node, source_lines, comment_line_set)

        return FunctionMetrics(
            name=fn_name,
            start_line=fn_node.start_point.row + 1,
            end_line=fn_node.end_point.row + 1,
            cyclomatic_complexity=cc,
            cognitive_complexity=cog,
            parameter_count=params,
            function_sloc=f_sloc,
        )

    # ------------------------------------------------------------------------
    # Metric 1: Cyclomatic Complexity (CC)
    # ------------------------------------------------------------------------
    def compute_cyclomatic_complexity(self, fn_node: tree_sitter.Node, language: str) -> int:
        """
        McCabe Cyclomatic Complexity: CC = 1 + sum(Decision Points).
        Excludes nested functions.
        """
        norm_lang = self.cst_manager.normalize_language(language)
        cc = 1

        nested_func_types = {
            "function_definition",
            "function_declaration",
            "arrow_function",
            "function_expression",
        }

        if norm_lang == LanguageType.PYTHON.value:
            decision_types = {
                "if_statement",
                "elif_clause",
                "for_statement",
                "while_statement",
                "except_clause",
                "conditional_expression",
                "match_clause",
            }

            def walk_py(node: tree_sitter.Node) -> None:
                nonlocal cc
                if node != fn_node and node.type in nested_func_types:
                    return

                if node.type in decision_types:
                    cc += 1
                elif node.type == "boolean_operator":
                    # 'and', 'or' operators add a branch
                    cc += 1

                for child in node.children:
                    walk_py(child)

            body = fn_node.child_by_field_name("body") or fn_node
            walk_py(body)

        else:
            # JavaScript / TypeScript / TSX
            decision_types = {
                "if_statement",
                "for_statement",
                "for_in_statement",
                "for_of_statement",
                "while_statement",
                "do_statement",
                "catch_clause",
                "ternary_expression",
            }

            def walk_js(node: tree_sitter.Node) -> None:
                nonlocal cc
                if node != fn_node and node.type in nested_func_types:
                    return

                if node.type in decision_types:
                    cc += 1
                elif node.type == "switch_case":
                    # Check if not default case
                    if any(c.type == "case" for c in node.children):
                        cc += 1
                elif node.type == "binary_expression":
                    op = node.child_by_field_name("operator")
                    if op and op.text and op.text.decode("utf-8") in ("&&", "||", "??"):
                        cc += 1

                for child in node.children:
                    walk_js(child)

            body = fn_node.child_by_field_name("body") or fn_node
            walk_js(body)

        return cc

    # ------------------------------------------------------------------------
    # Metric 2: Cognitive Complexity (SonarQube Specification)
    # ------------------------------------------------------------------------
    def compute_cognitive_complexity(self, fn_node: tree_sitter.Node, language: str) -> int:
        """
        Cognitive Complexity:
        - B1: Increments on flow breaks (+1).
        - B2: Nesting penalty for nesting (+current_nesting).
        - B3: Boolean sequences (+1).
        """
        norm_lang = self.cst_manager.normalize_language(language)
        score = 0

        nested_func_types = {
            "function_definition",
            "function_declaration",
            "arrow_function",
            "function_expression",
        }

        nesting_py = {"if_statement", "elif_clause", "for_statement", "while_statement", "except_clause"}
        nesting_js = {
            "if_statement",
            "for_statement",
            "for_in_statement",
            "for_of_statement",
            "while_statement",
            "do_statement",
            "catch_clause",
            "switch_statement",
        }
        nesting_set = nesting_py if norm_lang == LanguageType.PYTHON.value else nesting_js

        def walk(node: tree_sitter.Node, current_nesting: int) -> None:
            nonlocal score
            if node != fn_node and node.type in nested_func_types:
                return

            increases_nesting = False

            if node.type in nesting_set:
                score += (1 + current_nesting)
                increases_nesting = True
            elif node.type in ("conditional_expression", "ternary_expression"):
                score += (1 + current_nesting)
            elif node.type in ("boolean_operator", "binary_expression"):
                if norm_lang == LanguageType.PYTHON.value and node.type == "boolean_operator":
                    score += 1
                elif norm_lang != LanguageType.PYTHON.value and node.type == "binary_expression":
                    op = node.child_by_field_name("operator")
                    if op and op.text and op.text.decode("utf-8") in ("&&", "||", "??"):
                        score += 1

            next_nesting = current_nesting + (1 if increases_nesting else 0)
            for child in node.children:
                walk(child, next_nesting)

        body = fn_node.child_by_field_name("body") or fn_node
        walk(body, 0)
        return score

    # ------------------------------------------------------------------------
    # Metric 3: Parameter Count
    # ------------------------------------------------------------------------
    def compute_parameter_count(self, fn_node: tree_sitter.Node, language: str) -> int:
        """
        Count formal parameters, explicitly excluding 'self' and 'cls'.
        """
        norm_lang = self.cst_manager.normalize_language(language)
        params_node = fn_node.child_by_field_name("parameters")
        if not params_node:
            return 0

        count = 0
        if norm_lang == LanguageType.PYTHON.value:
            for child in params_node.children:
                if child.type in ("identifier", "typed_parameter", "default_parameter", "typed_default_parameter"):
                    p_name_node = child.child_by_field_name("name") or child
                    p_name = p_name_node.text.decode("utf-8", errors="replace") if p_name_node.text else ""
                    if p_name not in ("self", "cls"):
                        count += 1
                elif child.type in ("list_splat_pattern", "dictionary_splat_pattern"):
                    count += 1
        else:
            for child in params_node.children:
                if child.type in (
                    "identifier",
                    "required_parameter",
                    "optional_parameter",
                    "assignment_pattern",
                    "rest_pattern",
                ):
                    count += 1

        return count

    # ------------------------------------------------------------------------
    # Metric 4: Function SLOC
    # ------------------------------------------------------------------------
    def compute_function_sloc(
        self,
        fn_node: tree_sitter.Node,
        source_lines: List[str],
        comment_line_set: Set[int],
    ) -> int:
        """
        Count executable source lines of code in function boundaries (1-indexed).
        Excludes blank lines and comment lines.
        """
        start_row = fn_node.start_point.row + 1
        end_row = fn_node.end_point.row + 1
        sloc = 0

        for line_idx in range(start_row, min(end_row + 1, len(source_lines) + 1)):
            if line_idx in comment_line_set:
                continue
            line_str = source_lines[line_idx - 1].strip()
            if line_str:
                sloc += 1

        return max(sloc, 1)

    # ------------------------------------------------------------------------
    # Metric 5: File SLOC
    # ------------------------------------------------------------------------
    def compute_file_sloc(self, source_lines: List[str], comment_line_set: Set[int]) -> int:
        """
        Total non-empty, non-comment lines across entire file.
        """
        sloc = 0
        for idx, line in enumerate(source_lines, start=1):
            if idx in comment_line_set:
                continue
            if line.strip():
                sloc += 1
        return max(sloc, 1)

    # ------------------------------------------------------------------------
    # Metric 6: Module Coupling (Ce / Ca)
    # ------------------------------------------------------------------------
    def compute_module_coupling(
        self, tree: tree_sitter.Tree, language: str, ca_coupling: int = 0
    ) -> Tuple[int, int, float]:
        """
        Efferent Coupling (Ce): Number of external modules/files imported.
        Afferent Coupling (Ca): Number of workspace files importing this file.
        Instability (I) = Ce / (Ce + Ca).
        """
        norm_lang = self.cst_manager.normalize_language(language)
        ce = 0

        if norm_lang == LanguageType.PYTHON.value:
            import_nodes = self.cst_manager.find_all_by_type(
                tree.root_node, ["import_statement", "import_from_statement"]
            )
            for imp in import_nodes:
                if imp.type == "import_statement":
                    # Each dotted name is an import
                    names = [c for c in imp.children if c.type in ("dotted_name", "aliased_import")]
                    ce += max(len(names), 1)
                elif imp.type == "import_from_statement":
                    ce += 1
        else:
            import_nodes = self.cst_manager.find_all_by_type(
                tree.root_node, ["import_statement"]
            )
            ce += len(import_nodes)

            # Also check require(...) calls
            call_nodes = self.cst_manager.find_all_by_type(tree.root_node, ["call_expression"])
            for c in call_nodes:
                fn_node = c.child_by_field_name("function")
                if fn_node and fn_node.text and fn_node.text.decode("utf-8") == "require":
                    ce += 1

        ca = max(ca_coupling, 0)
        total = ce + ca
        instability = round(ce / total, 3) if total > 0 else 0.0
        return ce, ca, instability

    # ------------------------------------------------------------------------
    # Metric 7: Duplicated Blocks
    # ------------------------------------------------------------------------
    def compute_duplicated_blocks(
        self,
        tree: tree_sitter.Tree,
        source_lines: List[str],
        language: str,
        window_size: int = 4,
    ) -> int:
        """
        Detect duplicated blocks using statement-level rolling hashes or repeated non-trivial lines.
        """
        norm_lang = self.cst_manager.normalize_language(language)
        block_type = "block" if norm_lang == LanguageType.PYTHON.value else "statement_block"
        blocks = self.cst_manager.find_all_by_type(tree.root_node, [block_type])

        hash_counts: Dict[str, int] = {}
        dup_count = 0

        for b in blocks:
            stmts = [c for c in b.children if c.is_named and c.type not in (":", "{", "}", "comment")]
            if len(stmts) >= window_size:
                for i in range(len(stmts) - window_size + 1):
                    window = stmts[i : i + window_size]
                    norm_tokens = [w.type for w in window]
                    h = hashlib.sha256("::".join(norm_tokens).encode("utf-8")).hexdigest()
                    hash_counts[h] = hash_counts.get(h, 0) + 1
                    if hash_counts[h] == 2:
                        dup_count += 1

        # Fallback line-level duplicate check for small scripts
        if dup_count == 0:
            seen_lines: Dict[str, int] = {}
            for line in source_lines:
                s = line.strip()
                if len(s) > 20 and not s.startswith(("#", "//", "/*")):
                    seen_lines[s] = seen_lines.get(s, 0) + 1
                    if seen_lines[s] == 2:
                        dup_count += 1

        return dup_count

    # ------------------------------------------------------------------------
    # Metric 8: Comment Density
    # ------------------------------------------------------------------------
    def compute_comment_density(self, comment_lines_count: int, file_sloc: int) -> float:
        """
        Comment Density = comment_lines / (file_sloc + comment_lines).
        """
        total = file_sloc + comment_lines_count
        if total == 0:
            return 0.0
        return round(comment_lines_count / total, 3)

    def _extract_comment_lines(
        self, tree: tree_sitter.Tree, lines: List[str], language: str
    ) -> Set[int]:
        """
        Collect 1-indexed line numbers containing comments.
        """
        comment_lines: Set[int] = set()
        comment_nodes = self.cst_manager.get_comments(tree, language)

        for c_node in comment_nodes:
            start_row = c_node.start_point.row + 1
            end_row = c_node.end_point.row + 1
            for r in range(start_row, end_row + 1):
                comment_lines.add(r)

        # Fallback text check
        prefixes = ("#",) if language == LanguageType.PYTHON.value else ("//", "/*", "*")
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if any(stripped.startswith(p) for p in prefixes):
                comment_lines.add(idx)

        return comment_lines
