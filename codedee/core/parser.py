"""
CodeDEE - Stage 1: Multi-Language Concrete Syntax Tree (CST) Parser
Provides unified Tree-sitter parsing for Python, JavaScript, and TypeScript.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional, Literal

import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts

SupportedLanguage = Literal["python", "javascript", "typescript"]

# Initialize Languages and Parsers once at module load
_PY_LANG = Language(tspython.language())
_JS_LANG = Language(tsjs.language())
_TS_LANG = Language(tsts.language_typescript())

_PARSERS: dict[str, Parser] = {
    "python": Parser(_PY_LANG),
    "javascript": Parser(_JS_LANG),
    "typescript": Parser(_TS_LANG),
}


@dataclass
class FunctionEntity:
    """Represents an extracted function or method boundary."""
    name: str
    language: SupportedLanguage
    start_point: tuple[int, int]  # (row, col)
    end_point: tuple[int, int]
    start_byte: int
    end_byte: int
    parameters: list[str]
    code: str
    node: tree_sitter.Node


class CodeDEEParser:
    """Stage 1 Unified Tree-sitter CST Ingestion Engine."""

    @staticmethod
    def get_language_for_file(file_path: pathlib.Path | str) -> Optional[SupportedLanguage]:
        """Detect supported language from file extension."""
        ext = pathlib.Path(file_path).suffix.lower()
        if ext == ".py":
            return "python"
        elif ext in (".js", ".jsx", ".mjs"):
            return "javascript"
        elif ext in (".ts", ".tsx"):
            return "typescript"
        return None

    @staticmethod
    def normalize_language(lang_str: str) -> SupportedLanguage:
        norm = lang_str.lower().strip()
        if norm in ("py", "python"):
            return "python"
        elif norm in ("js", "javascript"):
            return "javascript"
        elif norm in ("ts", "typescript"):
            return "typescript"
        raise ValueError(f"Unsupported language: '{lang_str}'. CodeDEE supports Python, JavaScript, TypeScript.")

    @classmethod
    def parse_string(cls, code: str, language: str) -> tuple[tree_sitter.Tree, SupportedLanguage]:
        """Parse source code string into Tree-sitter CST."""
        lang = cls.normalize_language(language)
        parser = _PARSERS[lang]
        tree = parser.parse(code.encode("utf-8"))
        return tree, lang

    @classmethod
    def parse_file(cls, file_path: str | pathlib.Path, language: Optional[str] = None) -> tuple[tree_sitter.Tree, SupportedLanguage]:
        """Parse code from a file."""
        path = pathlib.Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")

        if not language:
            ext = path.suffix.lower()
            ext_map = {
                ".py": "python",
                ".js": "javascript",
                ".jsx": "javascript",
                ".mjs": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
            }
            language = ext_map.get(ext)
            if not language:
                raise ValueError(f"Cannot auto-detect language for file extension: '{ext}'")

        code = path.read_text(encoding="utf-8", errors="replace")
        return cls.parse_string(code, language)

    @classmethod
    def extract_functions(cls, code: str, language: str) -> list[FunctionEntity]:
        """
        Extract all function, method, and arrow-function declarations
        from the given code string, including parameter lists.
        """
        tree, lang = cls.parse_string(code, language)
        functions: list[FunctionEntity] = []
        code_bytes = code.encode("utf-8")

        def _traverse(node: tree_sitter.Node):
            ntype = node.type

            # Python function definitions
            if lang == "python" and ntype in ("function_definition", "async_function_definition"):
                name_node = node.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node and name_node.text else "anonymous"
                
                params_node = node.child_by_field_name("parameters")
                params = []
                if params_node:
                    for child in params_node.named_children:
                        if child.type in ("identifier", "typed_parameter", "default_parameter"):
                            p_name = child.child_by_field_name("name")
                            if p_name and p_name.text:
                                params.append(p_name.text.decode("utf-8"))
                            elif child.text:
                                params.append(child.text.decode("utf-8").split(":")[0].split("=")[0].strip())

                snippet = code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
                functions.append(
                    FunctionEntity(
                        name=name,
                        language=lang,
                        start_point=node.start_point,
                        end_point=node.end_point,
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                        parameters=params,
                        code=snippet,
                        node=node,
                    )
                )

            # JavaScript & TypeScript function definitions
            elif lang in ("javascript", "typescript") and ntype in (
                "function_declaration",
                "method_definition",
                "function_expression",
                "arrow_function",
            ):
                name = "anonymous"
                name_node = node.child_by_field_name("name")
                if name_node and name_node.text:
                    name = name_node.text.decode("utf-8")
                elif node.parent and node.parent.type == "variable_declarator":
                    var_name = node.parent.child_by_field_name("name")
                    if var_name and var_name.text:
                        name = var_name.text.decode("utf-8")

                params_node = node.child_by_field_name("parameters")
                params = []
                if params_node:
                    for child in params_node.named_children:
                        if child.type == "identifier" and child.text:
                            params.append(child.text.decode("utf-8"))
                        elif child.type in ("required_parameter", "optional_parameter"):
                            p_id = child.child_by_field_name("pattern") or child.child_by_field_name("name")
                            if p_id and p_id.text:
                                params.append(p_id.text.decode("utf-8"))

                snippet = code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
                functions.append(
                    FunctionEntity(
                        name=name,
                        language=lang,
                        start_point=node.start_point,
                        end_point=node.end_point,
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                        parameters=params,
                        code=snippet,
                        node=node,
                    )
                )

            for child in node.children:
                _traverse(child)

        _traverse(tree.root_node)
        return functions
