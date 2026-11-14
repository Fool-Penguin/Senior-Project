"""
CodeDEE - Semester 2: Project-Wide Symbol & Import Resolver
Indexes functions, classes, and exported symbols across a workspace directory
and resolves cross-module import paths for Python, JavaScript, and TypeScript.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tree_sitter
from codedee.core.parser import CodeDEEParser, FunctionEntity, SupportedLanguage


@dataclass
class ResolvedSymbol:
    """Represents an indexed function or symbol in the project."""
    symbol_id: str  # e.g., "app/routes.py:login"
    file_path: str  # relative path from project root
    function_name: str
    parameters: list[str]
    start_line: int
    end_line: int
    language: SupportedLanguage


@dataclass
class ImportedSymbol:
    """Represents an imported symbol inside a file."""
    local_name: str  # Alias or imported identifier
    source_module: str  # Relative or module path in import statement (e.g. "./db" or "app.services")
    original_name: str  # Original symbol name in source file
    line_number: int


class ProjectSymbolResolver:
    """
    Project-Wide Symbol & Import Resolver.
    Maintains a global symbol index and maps imported references to concrete files.
    """

    def __init__(self, project_root: Path | str):
        self.project_root = Path(project_root).resolve()
        self.symbols: dict[str, ResolvedSymbol] = {}  # symbol_id -> ResolvedSymbol
        self.function_lookup: dict[str, list[ResolvedSymbol]] = {}  # fn_name -> list of matches
        self.file_imports: dict[str, list[ImportedSymbol]] = {}  # file_rel_path -> imports
        self.file_trees: dict[str, tree_sitter.Tree] = {}

    def index_project(self, exclude_dirs: Optional[set[str]] = None):
        """Scan and index all Python, JavaScript, and TypeScript files in project_root."""
        excludes = exclude_dirs or {
            ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"
        }

        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in excludes for part in path.parts):
                continue

            lang_str = CodeDEEParser.get_language_for_file(path)
            if not lang_str:
                continue

            rel_path = path.relative_to(self.project_root).as_posix()
            try:
                code = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            self.index_file(rel_path, code, lang_str)

    def index_file(self, rel_path: str, code: str, language: str):
        """Index symbols and import statements for a single file."""
        tree, lang = CodeDEEParser.parse_string(code, language)
        self.file_trees[rel_path] = tree

        # 1. Extract and index functions
        functions = CodeDEEParser.extract_functions(code, lang)
        for fn in functions:
            sym_id = f"{rel_path}:{fn.name}"
            sym = ResolvedSymbol(
                symbol_id=sym_id,
                file_path=rel_path,
                function_name=fn.name,
                parameters=fn.parameters,
                start_line=fn.start_point[0] + 1,
                end_line=fn.end_point[0] + 1,
                language=lang,
            )
            self.symbols[sym_id] = sym
            self.function_lookup.setdefault(fn.name, []).append(sym)

        # 2. Extract import statements
        imports = self._extract_imports(tree, code, lang)
        self.file_imports[rel_path] = imports

    def _extract_imports(
        self, tree: tree_sitter.Tree, code: str, language: SupportedLanguage
    ) -> list[ImportedSymbol]:
        """Extract import bindings from CST."""
        imports: list[ImportedSymbol] = []
        root_node = tree.root_node

        def _traverse(node: tree_sitter.Node):
            # Python Imports
            if language == "python":
                # from module import symbol
                if node.type == "import_from_statement":
                    mod_node = node.child_by_field_name("module_name")
                    mod_name = mod_node.text.decode("utf-8") if mod_node else ""
                    for child in node.children:
                        if child.type == "dotted_name" and child != mod_node:
                            sym_name = child.text.decode("utf-8")
                            imports.append(
                                ImportedSymbol(
                                    local_name=sym_name,
                                    source_module=mod_name,
                                    original_name=sym_name,
                                    line_number=node.start_point[0] + 1,
                                )
                            )
                        elif child.type == "aliased_import":
                            name_node = child.child_by_field_name("name")
                            alias_node = child.child_by_field_name("alias")
                            orig = name_node.text.decode("utf-8") if name_node else ""
                            alias = alias_node.text.decode("utf-8") if alias_node else orig
                            imports.append(
                                ImportedSymbol(
                                    local_name=alias,
                                    source_module=mod_name,
                                    original_name=orig,
                                    line_number=node.start_point[0] + 1,
                                )
                            )

            # JavaScript / TypeScript Imports
            elif language in ("javascript", "typescript"):
                # import { x } from './module'
                if node.type == "import_statement":
                    src_node = node.child_by_field_name("source")
                    mod_path = src_node.text.decode("utf-8").strip("\"'") if src_node else ""
                    for child in node.children:
                        if child.type == "import_clause":
                            for clause_child in child.children:
                                if clause_child.type == "named_imports":
                                    for spec in clause_child.children:
                                        if spec.type == "import_specifier":
                                            name_node = spec.child_by_field_name("name")
                                            sym_name = name_node.text.decode("utf-8") if name_node else ""
                                            imports.append(
                                                ImportedSymbol(
                                                    local_name=sym_name,
                                                    source_module=mod_path,
                                                    original_name=sym_name,
                                                    line_number=node.start_point[0] + 1,
                                                )
                                            )
                                elif clause_child.type == "identifier":
                                    # Default import: import x from './module'
                                    sym_name = clause_child.text.decode("utf-8")
                                    imports.append(
                                        ImportedSymbol(
                                            local_name=sym_name,
                                            source_module=mod_path,
                                            original_name="default",
                                            line_number=node.start_point[0] + 1,
                                        )
                                    )

                # const x = require('./module')
                elif node.type == "variable_declarator":
                    val = node.child_by_field_name("value")
                    name = node.child_by_field_name("name")
                    if val and val.type == "call_expression":
                        fn = val.child_by_field_name("function")
                        if fn and fn.text == b"require":
                            args = val.child_by_field_name("arguments")
                            if args and len(args.children) >= 2:
                                mod_path = args.children[1].text.decode("utf-8").strip("\"'")
                                local_name = name.text.decode("utf-8") if name else ""
                                imports.append(
                                    ImportedSymbol(
                                        local_name=local_name,
                                        source_module=mod_path,
                                        original_name="*",
                                        line_number=node.start_point[0] + 1,
                                    )
                                )

            for c in node.children:
                _traverse(c)

        _traverse(root_node)
        return imports

    def resolve_callee(self, current_file: str, callee_name: str) -> Optional[ResolvedSymbol]:
        """
        Resolves a callee name called within current_file to a concrete project symbol.
        1. Checks intra-file function declarations.
        2. Checks explicitly imported bindings in current_file.
        3. Falls back to global project symbol lookup.
        """
        # 1. Intra-file check
        local_id = f"{current_file}:{callee_name}"
        if local_id in self.symbols:
            return self.symbols[local_id]

        # 2. Import bindings check
        imports = self.file_imports.get(current_file, [])
        for imp in imports:
            if imp.local_name == callee_name:
                # Find matching file for source_module
                target_file = self._resolve_module_path(current_file, imp.source_module)
                if target_file:
                    target_id = f"{target_file}:{imp.original_name}"
                    if target_id in self.symbols:
                        return self.symbols[target_id]

        # 3. Global unique lookup fallback
        matches = self.function_lookup.get(callee_name, [])
        if len(matches) == 1:
            return matches[0]

        return None

    def _resolve_module_path(self, current_file: str, module_str: str) -> Optional[str]:
        """Resolves an import string (e.g. './db' or 'app.services') to a relative file path."""
        curr_dir = Path(current_file).parent

        # Relative paths (JS/TS: ./db, ../utils)
        if module_str.startswith("."):
            candidate_base = (curr_dir / module_str).as_posix()
            for ext in [".js", ".ts", ".py", "/index.js", "/index.ts"]:
                cand = candidate_base + ext
                if any(cand == sym.file_path for sym in self.symbols.values()):
                    return cand

        # Python package paths (e.g. app.db -> app/db.py)
        py_path = module_str.replace(".", "/") + ".py"
        if any(sym.file_path == py_path for sym in self.symbols.values()):
            return py_path

        # Direct file prefix match
        for sym in self.symbols.values():
            if Path(sym.file_path).stem == Path(module_str).stem:
                return sym.file_path

        return None
