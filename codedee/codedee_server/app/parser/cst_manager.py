"""
cst_manager.py - Concrete Syntax Tree (CST) Manager using Tree-sitter.

Provides thread-safe language and parser management, syntax queries compatible
with Tree-sitter 0.26 via QueryCursor, and language detection across Python,
JavaScript, TypeScript, and TSX.
"""

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
import threading

import tree_sitter
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript


class LanguageType(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    TSX = "tsx"


class CSTParserManager:
    """
    Manager for Tree-sitter parsers, queries, and AST inspections.
    Compatible with Tree-sitter >= 0.22 / 0.26 API.
    """

    _instance: Optional["CSTParserManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._languages: Dict[str, tree_sitter.Language] = {}
        self._parsers: Dict[str, tree_sitter.Parser] = {}
        self._queries: Dict[Tuple[str, str], tree_sitter.Query] = {}
        self._alive_trees: Dict[int, Tuple[bytes, tree_sitter.Parser, tree_sitter.Tree]] = {}
        self._init_languages()

    @classmethod
    def get_instance(cls) -> "CSTParserManager":
        """Singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _init_languages(self) -> None:
        """Initialize language definitions and parsers."""
        py_lang = tree_sitter.Language(tree_sitter_python.language())
        js_lang = tree_sitter.Language(tree_sitter_javascript.language())
        ts_lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        tsx_lang = tree_sitter.Language(tree_sitter_typescript.language_tsx())

        self._languages[LanguageType.PYTHON.value] = py_lang
        self._languages["py"] = py_lang

        self._languages[LanguageType.JAVASCRIPT.value] = js_lang
        self._languages["js"] = js_lang

        self._languages[LanguageType.TYPESCRIPT.value] = ts_lang
        self._languages["ts"] = ts_lang

        self._languages[LanguageType.TSX.value] = tsx_lang

        for key, lang in list(self._languages.items()):
            self._parsers[key] = tree_sitter.Parser(lang)

    def normalize_language(self, language: Union[str, LanguageType]) -> str:
        """Map language string or enum to canonical name."""
        if isinstance(language, LanguageType):
            return language.value
        lang_str = str(language).strip().lower()
        if lang_str in ("py", "python", "python3"):
            return LanguageType.PYTHON.value
        elif lang_str in ("js", "javascript", "cjs", "mjs"):
            return LanguageType.JAVASCRIPT.value
        elif lang_str in ("tsx", "react_tsx"):
            return LanguageType.TSX.value
        elif lang_str in ("ts", "typescript"):
            return LanguageType.TYPESCRIPT.value
        return LanguageType.PYTHON.value

    def detect_language(
        self, file_path: Union[str, Path], code_content: Optional[Union[str, bytes]] = None
    ) -> str:
        """
        Detect programming language from file path extension or source content.
        Supports .py, .js, .mjs, .cjs, .ts, and .tsx.
        """
        path_str = str(file_path).lower()
        if path_str.endswith(".py"):
            return LanguageType.PYTHON.value
        elif path_str.endswith(".tsx"):
            return LanguageType.TSX.value
        elif path_str.endswith(".ts"):
            return LanguageType.TYPESCRIPT.value
        elif path_str.endswith((".js", ".mjs", ".cjs", ".jsx")):
            return LanguageType.JAVASCRIPT.value

        # Content sniffing fallback
        if code_content is not None:
            text = (
                code_content.decode("utf-8", errors="replace")
                if isinstance(code_content, bytes)
                else code_content
            )
            if "def " in text or ("import " in text and ":" in text):
                return LanguageType.PYTHON.value
            if "<" in text and ">" in text and ("className" in text or "</" in text or "/>" in text or "React" in text):
                return LanguageType.TSX.value
            if ": string" in text or ": number" in text or "interface " in text or ": boolean" in text:
                return LanguageType.TYPESCRIPT.value
            if "const " in text or "function " in text or "let " in text or "require(" in text:
                return LanguageType.JAVASCRIPT.value

        return LanguageType.PYTHON.value

    def get_language(self, language: Union[str, LanguageType]) -> tree_sitter.Language:
        """Return the compiled tree_sitter.Language for a given language."""
        norm = self.normalize_language(language)
        return self._languages[norm]

    def get_parser(self, language: Union[str, LanguageType]) -> tree_sitter.Parser:
        """Return a tree_sitter.Parser for a given language."""
        norm = self.normalize_language(language)
        return self._parsers[norm]

    def parse(
        self,
        code: Union[str, bytes],
        language: Optional[Union[str, LanguageType]] = None,
        file_path: Optional[Union[str, Path]] = None,
    ) -> tree_sitter.Tree:
        """
        Parse raw source code (str or bytes) into a Tree-sitter Tree.
        Pins the underlying source_bytes buffer and Parser in memory to guarantee
        that the C TSTree pointers remain valid throughout AST traversal.
        """
        if language is None:
            if file_path is not None:
                language = self.detect_language(file_path, code)
            else:
                language = LanguageType.PYTHON.value

        lang_obj = self.get_language(language)
        parser = tree_sitter.Parser(lang_obj)
        source_bytes = code.encode("utf-8") if isinstance(code, str) else code
        tree = parser.parse(source_bytes)

        with self._lock:
            if len(self._alive_trees) > 500:
                keys_to_remove = list(self._alive_trees.keys())[:200]
                for k in keys_to_remove:
                    self._alive_trees.pop(k, None)
            self._alive_trees[id(tree)] = (source_bytes, parser, tree)

        return tree

    def get_query(self, language: Union[str, LanguageType], query_scm: str) -> tree_sitter.Query:
        """
        Compile and cache a tree-sitter Query.
        """
        norm = self.normalize_language(language)
        key = (norm, query_scm.strip())
        if key not in self._queries:
            lang_obj = self.get_language(norm)
            self._queries[key] = tree_sitter.Query(lang_obj, query_scm)
        return self._queries[key]

    def query_captures(
        self,
        query: Union[tree_sitter.Query, str],
        node: tree_sitter.Node,
        language: Optional[Union[str, LanguageType]] = None,
    ) -> Dict[str, List[tree_sitter.Node]]:
        """
        Execute Tree-sitter query captures against a node.
        Complies strictly with Tree-sitter 0.26 by routing through QueryCursor(query).
        Returns a dict mapping capture name -> list of matching Nodes.
        """
        if isinstance(query, str):
            if language is None:
                raise ValueError("language must be provided when query is a string")
            query_obj = self.get_query(language, query)
        else:
            query_obj = query

        cursor = tree_sitter.QueryCursor(query_obj)
        return cursor.captures(node)

    def query_matches(
        self,
        query: Union[tree_sitter.Query, str],
        node: tree_sitter.Node,
        language: Optional[Union[str, LanguageType]] = None,
    ) -> List[Tuple[int, Dict[str, List[tree_sitter.Node]]]]:
        """
        Execute Tree-sitter query matches against a node.
        Complies strictly with Tree-sitter 0.26 by routing through QueryCursor(query).
        Returns a list of (pattern_index, captures_dict).
        """
        if isinstance(query, str):
            if language is None:
                raise ValueError("language must be provided when query is a string")
            query_obj = self.get_query(language, query)
        else:
            query_obj = query

        cursor = tree_sitter.QueryCursor(query_obj)
        return cursor.matches(node)

    @staticmethod
    def get_node_text(node: Optional[tree_sitter.Node], source_bytes: Optional[bytes] = None) -> str:
        """Extract decoded utf-8 text of an AST node safely."""
        if node is None:
            return ""
        if source_bytes is not None:
            try:
                sb = node.start_byte
                eb = node.end_byte
                if sb is not None and eb is not None and 0 <= sb <= eb <= len(source_bytes):
                    return source_bytes[sb:eb].decode("utf-8", errors="replace")
            except Exception:
                pass
            return ""
        try:
            val = getattr(node, "text", None)
            if val is not None and isinstance(val, (bytes, bytearray)):
                return val.decode("utf-8", errors="replace")
        except Exception:
            pass
        return ""

    @staticmethod
    def get_node_point(node: Optional[tree_sitter.Node], source_bytes: Optional[bytes] = None) -> Tuple[int, int]:
        """
        Extract (1-indexed line, 0-indexed column) safely without allocating tree_sitter.Point
        objects in C that can trigger heap corruption on Windows Python 3.14.
        """
        if node is None:
            return 1, 0
        if source_bytes is not None:
            try:
                sb = node.start_byte
                if sb is not None and 0 <= sb <= len(source_bytes):
                    prefix = source_bytes[:sb]
                    line = prefix.count(b"\n") + 1
                    last_nl = prefix.rfind(b"\n")
                    col = sb if last_nl == -1 else sb - last_nl - 1
                    return line, col
            except Exception:
                pass
        try:
            sp = node.start_point
            return sp.row + 1, sp.column
        except Exception:
            return 1, 0

    @staticmethod
    def get_node_end_point(node: Optional[tree_sitter.Node], source_bytes: Optional[bytes] = None) -> Tuple[int, int]:
        """
        Extract (1-indexed end_line, 0-indexed end_column) safely.
        """
        if node is None:
            return 1, 0
        if source_bytes is not None:
            try:
                eb = node.end_byte
                if eb is not None and 0 <= eb <= len(source_bytes):
                    prefix = source_bytes[:eb]
                    line = prefix.count(b"\n") + 1
                    last_nl = prefix.rfind(b"\n")
                    col = eb if last_nl == -1 else eb - last_nl - 1
                    return line, col
            except Exception:
                pass
        try:
            ep = node.end_point
            return ep.row + 1, ep.column
        except Exception:
            return 1, 0

    @staticmethod
    def has_syntax_errors(target: Union[tree_sitter.Tree, tree_sitter.Node]) -> bool:
        """Check whether the tree or node has syntax errors or missing tokens."""
        node = target.root_node if isinstance(target, tree_sitter.Tree) else target
        if node.has_error or node.is_missing:
            return True
        return False

    @staticmethod
    def find_all_by_type(
        node: tree_sitter.Node, target_types: Union[Set[str], List[str]]
    ) -> List[tree_sitter.Node]:
        """Breadth-first search for all nodes matching specified type names."""
        types_set = set(target_types)
        results: List[tree_sitter.Node] = []
        queue = [node]
        while queue:
            curr = queue.pop(0)
            if curr.type in types_set:
                results.append(curr)
            queue.extend(curr.children)
        return results

    def get_comments(self, tree: tree_sitter.Tree, language: str) -> List[tree_sitter.Node]:
        """Collect all comment nodes for the given CST."""
        return self.find_all_by_type(tree.root_node, {"comment"})

    def get_functions(self, tree: tree_sitter.Tree, language: str) -> List[tree_sitter.Node]:
        """Extract all function definitions for the given CST."""
        norm = self.normalize_language(language)
        if norm == LanguageType.PYTHON.value:
            fn_types = {"function_definition"}
        else:
            fn_types = {
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_definition",
            }
        return self.find_all_by_type(tree.root_node, fn_types)
