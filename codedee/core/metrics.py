"""
CodeDEE - Stage 3A: Maintainability Metrics Engine (ISO/IEC 25010)
Calculates the 8 official maintainability metrics across Python, JavaScript, and TypeScript
without using legacy SQALE ratings:

Function-level (4):
1. Cyclomatic Complexity (CC)
2. Cognitive Complexity
3. Parameter Count
4. Function SLOC

File-level (4):
5. File SLOC
6. Module Coupling (Afferent Ca / Efferent Ce)
7. Duplicated Blocks
8. Comment Density
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
import tree_sitter

from codedee.core.parser import CodeDEEParser, FunctionEntity, SupportedLanguage


@dataclass
class FunctionMetrics:
    name: str
    cyclomatic_complexity: int
    cognitive_complexity: int
    parameter_count: int
    sloc: int


@dataclass
class FileMetrics:
    language: SupportedLanguage
    file_sloc: int
    comment_density: float  # Percentage 0.0 - 100.0
    module_coupling_ce: int  # Efferent coupling (outgoing imports)
    module_coupling_ca: int  # Afferent coupling (incoming references)
    duplicated_blocks_count: int
    functions: list[FunctionMetrics] = field(default_factory=list)


class MaintainabilityEngine:
    """Stage 3A ISO/IEC 25010 Maintainability Calculator."""

    @classmethod
    def analyze_code(cls, code: str, language: str) -> FileMetrics:
        """Analyze code string and compute all 8 maintainability metrics."""
        tree, lang = CodeDEEParser.parse_string(code, language)
        functions = CodeDEEParser.extract_functions(code, lang)

        # File-level metrics
        lines = code.splitlines()
        file_sloc, comment_density = cls._calc_sloc_and_comments(lines, lang)
        ce, ca = cls._calc_coupling(tree, lang)
        dup_blocks = cls._detect_duplicated_blocks(lines)

        # Function-level metrics
        fn_metrics: list[FunctionMetrics] = []
        for fn in functions:
            cc = cls._calc_cyclomatic_complexity(fn.node, lang)
            cog = cls._calc_cognitive_complexity(fn.node, lang)
            param_cnt = len(fn.parameters)
            fn_sloc = cls._calc_function_sloc(fn.code, lang)

            fn_metrics.append(
                FunctionMetrics(
                    name=fn.name,
                    cyclomatic_complexity=cc,
                    cognitive_complexity=cog,
                    parameter_count=param_cnt,
                    sloc=fn_sloc,
                )
            )

        return FileMetrics(
            language=lang,
            file_sloc=file_sloc,
            comment_density=round(comment_density, 2),
            module_coupling_ce=ce,
            module_coupling_ca=ca,
            duplicated_blocks_count=dup_blocks,
            functions=fn_metrics,
        )

    @staticmethod
    def _calc_sloc_and_comments(lines: list[str], language: SupportedLanguage) -> tuple[int, float]:
        """Calculate Source Lines of Code (SLOC) and Comment Density percentage."""
        sloc = 0
        comment_lines = 0
        in_block_comment = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            if language == "python":
                if line.startswith("#"):
                    comment_lines += 1
                elif line.startswith('"""') or line.startswith("'''"):
                    comment_lines += 1
                    if line.count('"""') == 1 or line.count("'''") == 1:
                        in_block_comment = not in_block_comment
                elif in_block_comment:
                    comment_lines += 1
                    if '"""' in line or "'''" in line:
                        in_block_comment = False
                else:
                    sloc += 1
            else:  # JS / TS
                if line.startswith("//"):
                    comment_lines += 1
                elif line.startswith("/*"):
                    comment_lines += 1
                    if "*/" not in line:
                        in_block_comment = True
                elif in_block_comment:
                    comment_lines += 1
                    if "*/" in line:
                        in_block_comment = False
                else:
                    sloc += 1

        total_meaningful = sloc + comment_lines
        density = (comment_lines / total_meaningful * 100.0) if total_meaningful > 0 else 0.0
        return max(1, sloc), density

    @staticmethod
    def _calc_function_sloc(fn_code: str, language: SupportedLanguage) -> int:
        lines = fn_code.splitlines()
        sloc, _ = MaintainabilityEngine._calc_sloc_and_comments(lines, language)
        return sloc

    @staticmethod
    def _calc_cyclomatic_complexity(node: tree_sitter.Node, language: SupportedLanguage) -> int:
        """
        McCabe Cyclomatic Complexity:
        Base = 1 + Decision points (if, for, while, case, logical operators &&, ||, and, or).
        """
        cc = 1
        decision_types = {
            "if_statement",
            "elif_clause",
            "for_statement",
            "while_statement",
            "catch_clause",
            "except_clause",
            "conditional_expression",  # ternary ?:
        }

        def _walk(n: tree_sitter.Node):
            nonlocal cc
            if n.type in decision_types:
                cc += 1
            # Check boolean operators
            elif n.type in ("binary_operator", "boolean_operator"):
                op = n.child_by_field_name("operator")
                if op and op.text and op.text.decode("utf-8") in ("&&", "||", "and", "or"):
                    cc += 1

            for child in n.children:
                _walk(child)

        _walk(node)
        return cc

    @staticmethod
    def _calc_cognitive_complexity(node: tree_sitter.Node, language: SupportedLanguage) -> int:
        """
        Sonar-style Cognitive Complexity:
        Increments by 1 + current nesting level for nested structural breaks.
        """
        cog = 0

        def _walk(n: tree_sitter.Node, nesting: int):
            nonlocal cog
            increments = 0
            new_nesting = nesting

            if n.type in ("if_statement", "for_statement", "while_statement", "catch_clause", "except_clause"):
                increments = 1 + nesting
                new_nesting = nesting + 1
            elif n.type in ("elif_clause", "else_clause"):
                increments = 1

            cog += increments
            for child in n.children:
                _walk(child, new_nesting)

        _walk(node, 0)
        return cog

    @staticmethod
    def _calc_coupling(tree: tree_sitter.Tree, language: SupportedLanguage) -> tuple[int, int]:
        """
        Calculate module coupling:
        Ce (Efferent): count of external import statements.
        Ca (Afferent): incoming references (initialized to 0 for standalone file analysis).
        """
        ce = 0
        import_types = {
            "import_statement",
            "import_from_statement",
            "import_declaration",  # JS/TS
        }

        def _walk(n: tree_sitter.Node):
            nonlocal ce
            if n.type in import_types:
                ce += 1
            elif n.type == "call_expression":
                # Check require() in JS
                fn = n.child_by_field_name("function")
                if fn and fn.text and fn.text.decode("utf-8") == "require":
                    ce += 1

            for child in n.children:
                _walk(child)

        _walk(tree.root_node)
        return ce, 0

    @staticmethod
    def _detect_duplicated_blocks(lines: list[str], min_block_size: int = 4) -> int:
        """Count identical consecutive code blocks of at least min_block_size lines."""
        clean_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith(("#", "//", "/*", "*"))]
        if len(clean_lines) < min_block_size * 2:
            return 0

        seen_blocks = set()
        duplicates = 0
        for i in range(len(clean_lines) - min_block_size + 1):
            block_tuple = tuple(clean_lines[i : i + min_block_size])
            if block_tuple in seen_blocks:
                duplicates += 1
            else:
                seen_blocks.add(block_tuple)

        return duplicates
