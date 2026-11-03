"""
call_graph.py - Inter-procedural and cross-file Call Graph builder using NetworkX.

Constructs directed graphs representing function definitions and invocation sites
with support for intra-file and cross-file symbol and import resolution across
Python, JavaScript, and TypeScript.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx
import tree_sitter

from ..parser.cst_manager import CSTParserManager, LanguageType


class CallGraphBuilder:
    """
    Constructs an inter-procedural, cross-file Call Graph as a NetworkX DiGraph.
    """

    def __init__(self) -> None:
        self.cst_manager = CSTParserManager.get_instance()
        self.graph: nx.DiGraph = nx.DiGraph()
        # file_path -> {func_name: func_metadata}
        self.file_declarations: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # file_path -> {imported_symbol: (resolved_file_path, target_symbol)}
        self.file_imports: Dict[str, Dict[str, Tuple[Optional[str], str]]] = {}
        # file_path -> [raw_call_site_data]
        self.pending_calls: Dict[str, List[Dict[str, Any]]] = {}
        # file_path -> source code text
        self.file_sources: Dict[str, str] = {}
        # file_path -> language
        self.file_languages: Dict[str, str] = {}

    def add_file(
        self,
        file_path: str,
        code: Optional[str] = None,
        language: Optional[str] = None,
    ) -> None:
        """
        Ingest and index a single source file into the call graph.
        """
        norm_path = os.path.normpath(file_path).replace("\\", "/")
        if code is None:
            if not os.path.exists(file_path):
                return
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()

        lang = language or self.cst_manager.detect_language(norm_path, code)
        self.file_sources[norm_path] = code
        self.file_languages[norm_path] = lang
        self.file_declarations[norm_path] = {}
        self.file_imports[norm_path] = {}
        self.pending_calls[norm_path] = []

        tree = self.cst_manager.parse(code, lang)
        self._extract_declarations(norm_path, lang, tree.root_node, code.encode("utf-8"))
        self._extract_imports(norm_path, lang, tree.root_node, code.encode("utf-8"))
        self._extract_calls(norm_path, lang, tree.root_node, code.encode("utf-8"))

    def add_workspace(self, directory: str) -> None:
        """
        Recursively scan and ingest all Python, JS, and TS files in a workspace directory.
        """
        norm_dir = os.path.normpath(os.path.abspath(directory))
        valid_exts = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx")
        ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

        for root, dirs, files in os.walk(norm_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if any(file.lower().endswith(ext) for ext in valid_exts):
                    file_path = os.path.join(root, file)
                    self.add_file(file_path)

    def _extract_declarations(
        self,
        file_path: str,
        language: str,
        root_node: tree_sitter.Node,
        source_bytes: bytes,
    ) -> None:
        """Extract functions, methods, parameters, and entry-point markers."""
        norm_lang = self.cst_manager.normalize_language(language)

        if norm_lang == LanguageType.PYTHON.value:
            # Query python functions
            fn_nodes = self.cst_manager.find_all_by_type(root_node, ["function_definition"])
            for fn in fn_nodes:
                name_node = fn.child_by_field_name("name")
                if not name_node:
                    continue
                name = self.cst_manager.get_node_text(name_node, source_bytes)
                params_node = fn.child_by_field_name("parameters")
                params: List[str] = []
                if params_node:
                    for child in params_node.named_children:
                        p_name = None
                        if child.type in ("identifier", "required_parameter", "optional_parameter"):
                            p_name_node = child.child_by_field_name("pattern") or child.child_by_field_name("name") or child
                            p_name = self.cst_manager.get_node_text(p_name_node, source_bytes)
                        elif child.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
                            p_name_node = child.child_by_field_name("name") or (child.child(0) if child.child_count > 0 else None)
                            if p_name_node:
                                p_name = self.cst_manager.get_node_text(p_name_node, source_bytes)
                        if p_name and p_name not in (",", "(", ")", ":", "self", "cls"):
                            params.append(p_name)

                # Check entry-point decorators
                is_entry = False
                prev = fn.prev_sibling
                while prev and prev.type == "decorator":
                    dec_text = self.cst_manager.get_node_text(prev, source_bytes)
                    if any(kw in dec_text for kw in ["route", "get", "post", "put", "delete", "endpoint", "api"]):
                        is_entry = True
                    prev = prev.prev_sibling

                # Extract docstring if present
                docstring = None
                body = fn.child_by_field_name("body")
                if body and len(body.children) > 0:
                    first_stmt = body.children[0]
                    if first_stmt.type == "expression_statement":
                        expr = first_stmt.children[0]
                        if expr.type == "string":
                            docstring = self.cst_manager.get_node_text(expr, source_bytes).strip("\"' \n")

                node_id = f"{file_path}::{name}"
                decl_info = {
                    "node_id": node_id,
                    "file_path": file_path,
                    "language": norm_lang,
                    "name": name,
                    "qualified_name": name,
                    "start_line": fn.start_point.row + 1,
                    "end_line": fn.end_point.row + 1,
                    "is_entry_point": is_entry,
                    "is_external": False,
                    "parameters": params,
                    "docstring": docstring,
                    "ast_node": None,
                }
                self.file_declarations[file_path][name] = decl_info
                self.graph.add_node(node_id, **decl_info)

        else:
            # JS / TS / TSX
            fn_types = ["function_declaration", "method_definition"]
            for fn in self.cst_manager.find_all_by_type(root_node, fn_types):
                name_node = fn.child_by_field_name("name")
                if not name_node:
                    continue
                name = self.cst_manager.get_node_text(name_node, source_bytes)
                params_node = fn.child_by_field_name("parameters")
                params: List[str] = []
                if params_node:
                    for child in params_node.children:
                        if child.type in ("identifier", "required_parameter", "optional_parameter"):
                            p_name = child.child_by_field_name("pattern") or child.child_by_field_name("name") or child
                            params.append(self.cst_manager.get_node_text(p_name, source_bytes))

                node_id = f"{file_path}::{name}"
                decl_info = {
                    "node_id": node_id,
                    "file_path": file_path,
                    "language": norm_lang,
                    "name": name,
                    "qualified_name": name,
                    "start_line": fn.start_point.row + 1,
                    "end_line": fn.end_point.row + 1,
                    "is_entry_point": False,
                    "is_external": False,
                    "parameters": params,
                    "docstring": None,
                    "ast_node": None,
                }
                self.file_declarations[file_path][name] = decl_info
                self.graph.add_node(node_id, **decl_info)

            # Also handle const foo = (params) => { ... } or function expressions
            var_decls = self.cst_manager.find_all_by_type(root_node, ["variable_declarator"])
            for var in var_decls:
                name_node = var.child_by_field_name("name")
                val_node = var.child_by_field_name("value")
                if name_node and val_node and val_node.type in ("arrow_function", "function_expression"):
                    name = self.cst_manager.get_node_text(name_node, source_bytes)
                    params_node = val_node.child_by_field_name("parameters")
                    params = []
                    if params_node:
                        for child in params_node.children:
                            if child.type in ("identifier", "required_parameter", "optional_parameter"):
                                p_name = child.child_by_field_name("pattern") or child.child_by_field_name("name") or child
                                params.append(self.cst_manager.get_node_text(p_name, source_bytes))

                    node_id = f"{file_path}::{name}"
                    decl_info = {
                        "node_id": node_id,
                        "file_path": file_path,
                        "language": norm_lang,
                        "name": name,
                        "qualified_name": name,
                        "start_line": var.start_point.row + 1,
                        "end_line": var.end_point.row + 1,
                        "is_entry_point": False,
                        "is_external": False,
                        "parameters": params,
                        "docstring": None,
                        "ast_node": None,
                    }
                    self.file_declarations[file_path][name] = decl_info
                    self.graph.add_node(node_id, **decl_info)

    def _extract_imports(
        self,
        file_path: str,
        language: str,
        root_node: tree_sitter.Node,
        source_bytes: bytes,
    ) -> None:
        """Parse import statements and resolve module references."""
        norm_lang = self.cst_manager.normalize_language(language)
        file_dir = os.path.dirname(file_path)

        if norm_lang == LanguageType.PYTHON.value:
            # from module import symbol [as alias]
            import_froms = self.cst_manager.find_all_by_type(root_node, ["import_from_statement"])
            for imp in import_froms:
                mod_node = imp.child_by_field_name("module_name")
                mod_name = self.cst_manager.get_node_text(mod_node, source_bytes) if mod_node else ""
                
                # Check for relative import dots
                dots = 0
                for c in imp.children:
                    if c.type == "relative_import":
                        # relative import node contains dots
                        dots_text = self.cst_manager.get_node_text(c, source_bytes)
                        dots = dots_text.count(".")
                    elif c.type == "import_prefix":
                        dots_text = self.cst_manager.get_node_text(c, source_bytes)
                        dots = dots_text.count(".")

                target_file = self._resolve_python_module(file_dir, mod_name, dots)

                # Process imported symbols
                for child in imp.children:
                    if child.type == "dotted_name" and child != mod_node:
                        sym = self.cst_manager.get_node_text(child, source_bytes)
                        self.file_imports[file_path][sym] = (target_file, sym)
                    elif child.type == "aliased_import":
                        orig = child.child_by_field_name("name")
                        alias = child.child_by_field_name("alias")
                        if orig and alias:
                            orig_sym = self.cst_manager.get_node_text(orig, source_bytes)
                            alias_sym = self.cst_manager.get_node_text(alias, source_bytes)
                            self.file_imports[file_path][alias_sym] = (target_file, orig_sym)

            # import module [as alias]
            imports = self.cst_manager.find_all_by_type(root_node, ["import_statement"])
            for imp in imports:
                for child in imp.children:
                    if child.type == "dotted_name":
                        mod = self.cst_manager.get_node_text(child, source_bytes)
                        target_file = self._resolve_python_module(file_dir, mod, 0)
                        self.file_imports[file_path][mod] = (target_file, mod)
                    elif child.type == "aliased_import":
                        orig = child.child_by_field_name("name")
                        alias = child.child_by_field_name("alias")
                        if orig and alias:
                            orig_mod = self.cst_manager.get_node_text(orig, source_bytes)
                            alias_name = self.cst_manager.get_node_text(alias, source_bytes)
                            target_file = self._resolve_python_module(file_dir, orig_mod, 0)
                            self.file_imports[file_path][alias_name] = (target_file, orig_mod)

        else:
            # JS / TS import statements
            # import { foo as bar } from './module';
            # import foo from './module';
            # const foo = require('./module');
            imports = self.cst_manager.find_all_by_type(root_node, ["import_statement"])
            for imp in imports:
                source_node = imp.child_by_field_name("source")
                if not source_node:
                    continue
                raw_mod = self.cst_manager.get_node_text(source_node, source_bytes).strip("\"'")
                target_file = self._resolve_js_module(file_dir, raw_mod)

                # Find imported clause
                for child in imp.children:
                    if child.type == "import_clause":
                        for sub in child.children:
                            if sub.type == "identifier":
                                sym = self.cst_manager.get_node_text(sub, source_bytes)
                                self.file_imports[file_path][sym] = (target_file, "default")
                            elif sub.type == "named_imports":
                                for spec in sub.children:
                                    if spec.type == "import_specifier":
                                        name = spec.child_by_field_name("name")
                                        alias = spec.child_by_field_name("alias")
                                        if name:
                                            orig_sym = self.cst_manager.get_node_text(name, source_bytes)
                                            used_sym = self.cst_manager.get_node_text(alias, source_bytes) if alias else orig_sym
                                            self.file_imports[file_path][used_sym] = (target_file, orig_sym)

            # CommonJS require(...)
            calls = self.cst_manager.find_all_by_type(root_node, ["call_expression"])
            for call in calls:
                fn_node = call.child_by_field_name("function")
                if fn_node and self.cst_manager.get_node_text(fn_node, source_bytes) == "require":
                    args = call.child_by_field_name("arguments")
                    if args and len(args.children) > 1:
                        raw_mod = self.cst_manager.get_node_text(args.children[1], source_bytes).strip("\"'")
                        target_file = self._resolve_js_module(file_dir, raw_mod)
                        parent = call.parent
                        if parent and parent.type == "variable_declarator":
                            name_node = parent.child_by_field_name("name")
                            if name_node:
                                if name_node.type == "identifier":
                                    sym = self.cst_manager.get_node_text(name_node, source_bytes)
                                    self.file_imports[file_path][sym] = (target_file, "*")
                                elif name_node.type == "object_pattern":
                                    for prop in name_node.children:
                                        if prop.type in ("shorthand_property_identifier_pattern", "identifier"):
                                            s = self.cst_manager.get_node_text(prop, source_bytes)
                                            self.file_imports[file_path][s] = (target_file, s)

    def _resolve_python_module(self, current_dir: str, module_name: str, relative_dots: int) -> Optional[str]:
        """Resolve a Python module path relative to current directory or workspace."""
        base_dir = current_dir
        if relative_dots > 1:
            for _ in range(relative_dots - 1):
                base_dir = os.path.dirname(base_dir)

        # Candidates: base_dir/module_name.py, base_dir/module_name/__init__.py
        cand1 = os.path.normpath(os.path.join(base_dir, f"{module_name.replace('.', os.sep)}.py"))
        cand2 = os.path.normpath(os.path.join(base_dir, module_name.replace('.', os.sep), "__init__.py"))
        cand3 = os.path.normpath(os.path.join(base_dir, f"{module_name}.py"))

        for c in (cand1, cand2, cand3):
            if os.path.isfile(c):
                return os.path.normpath(c).replace("\\", "/")

        # Check known ingested files
        for ingested_file in self.file_sources.keys():
            base_cand = os.path.basename(ingested_file)
            if base_cand in (f"{module_name}.py", f"{module_name.split('.')[-1]}.py"):
                return ingested_file.replace("\\", "/")

        return None

    def _resolve_js_module(self, current_dir: str, module_path: str) -> Optional[str]:
        """Resolve a JS/TS module path relative to current directory or workspace."""
        if not module_path.startswith((".", "/")):
            # External npm package
            return None

        clean_path = os.path.normpath(os.path.join(current_dir, module_path))
        candidates = [
            clean_path,
            f"{clean_path}.ts",
            f"{clean_path}.tsx",
            f"{clean_path}.js",
            f"{clean_path}.mjs",
            os.path.join(clean_path, "index.ts"),
            os.path.join(clean_path, "index.tsx"),
            os.path.join(clean_path, "index.js"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return os.path.normpath(c).replace("\\", "/")

        for ingested_file in self.file_sources.keys():
            stem = Path(ingested_file).stem
            mod_stem = Path(module_path).stem
            if stem == mod_stem:
                return ingested_file

        return None

    def _find_enclosing_function(
        self, node: tree_sitter.Node, source_bytes: bytes, file_path: str
    ) -> Optional[str]:
        """Find the name of the function enclosing an AST node."""
        curr = node.parent
        while curr:
            if curr.type in (
                "function_definition",
                "function_declaration",
                "method_definition",
            ):
                name_node = curr.child_by_field_name("name")
                if name_node:
                    return self.cst_manager.get_node_text(name_node, source_bytes)
            elif curr.type == "variable_declarator":
                val = curr.child_by_field_name("value")
                if val and val.type in ("arrow_function", "function_expression"):
                    name_node = curr.child_by_field_name("name")
                    if name_node:
                        return self.cst_manager.get_node_text(name_node, source_bytes)
            curr = curr.parent
        return None

    def _extract_calls(
        self,
        file_path: str,
        language: str,
        root_node: tree_sitter.Node,
        source_bytes: bytes,
    ) -> None:
        """Find all call expressions and store as pending calls for resolution."""
        norm_lang = self.cst_manager.normalize_language(language)
        call_types = ["call"] if norm_lang == LanguageType.PYTHON.value else ["call_expression"]
        call_nodes = self.cst_manager.find_all_by_type(root_node, call_types)

        for call in call_nodes:
            fn_node = call.child_by_field_name("function")
            if not fn_node:
                continue

            enclosing_func = self._find_enclosing_function(call, source_bytes, file_path)
            call_expr = self.cst_manager.get_node_text(call, source_bytes)
            fn_text = self.cst_manager.get_node_text(fn_node, source_bytes)

            args_node = call.child_by_field_name("arguments")
            arguments: List[str] = []
            if args_node:
                for arg in args_node.children:
                    if arg.type not in ("(", ")", ",", "[", "]", "{", "}"):
                        arguments.append(self.cst_manager.get_node_text(arg, source_bytes))

            self.pending_calls[file_path].append({
                "file_path": file_path,
                "caller_name": enclosing_func or "<module>",
                "callee_text": fn_text,
                "call_line": call.start_point.row + 1,
                "call_col": call.start_point.column,
                "call_expression": call_expr,
                "arguments": arguments,
                "ast_node": None,
            })

    def build(self) -> nx.DiGraph:
        """
        Resolve pending call sites to actual declared functions or external targets
        and add directed edges in the Call Graph.
        """
        for file_path, calls in self.pending_calls.items():
            for call_info in calls:
                caller_name = call_info["caller_name"]
                caller_id = f"{file_path}::{caller_name}"

                # Ensure caller node exists
                if caller_id not in self.graph:
                    self.graph.add_node(
                        caller_id,
                        file_path=file_path,
                        name=caller_name,
                        qualified_name=caller_name,
                        is_external=False,
                        is_entry_point=(caller_name == "<module>"),
                        start_line=1,
                        end_line=1,
                        parameters=[],
                    )

                callee_text = call_info["callee_text"]
                callee_id, callee_params = self._resolve_callee(file_path, callee_text)

                # Compute arg mapping to callee parameters
                arg_mapping: Dict[int, str] = {}
                for idx, arg in enumerate(call_info["arguments"]):
                    if idx < len(callee_params):
                        arg_mapping[idx] = callee_params[idx]
                    else:
                        arg_mapping[idx] = f"arg_{idx}"

                edge_attrs = {
                    "call_line": call_info["call_line"],
                    "call_col": call_info["call_col"],
                    "call_expression": call_info["call_expression"],
                    "arguments": call_info["arguments"],
                    "arg_mapping": arg_mapping,
                    "is_dynamic": False,
                }
                self.graph.add_edge(caller_id, callee_id, **edge_attrs)

        return self.graph

    def _resolve_callee(self, file_path: str, callee_text: str) -> Tuple[str, List[str]]:
        """
        Resolve callee text to a concrete node_id and formal parameter list.
        Handles:
        1. Local function within file: foo()
        2. Imported function: foo() where foo is in self.file_imports
        3. Module method: mod.foo() where mod is in self.file_imports
        4. Cross-file declared functions in workspace
        5. External API / standard library (e.g. cursor.execute, db.query)
        """
        # Case 1: Local function
        if file_path in self.file_declarations and callee_text in self.file_declarations[file_path]:
            decl = self.file_declarations[file_path][callee_text]
            return decl["node_id"], decl.get("parameters", [])

        # Case 2: Imported directly (from module import func)
        imports = self.file_imports.get(file_path, {})
        if callee_text in imports:
            target_file, target_sym = imports[callee_text]
            if target_file and target_file in self.file_declarations:
                if target_sym in self.file_declarations[target_file]:
                    decl = self.file_declarations[target_file][target_sym]
                    return decl["node_id"], decl.get("parameters", [])
            if target_file:
                target_id = f"{target_file}::{target_sym}"
                return target_id, []

        # Case 3: Method call on imported module: module.func()
        if "." in callee_text:
            parts = callee_text.split(".")
            mod_prefix = parts[0]
            member_name = parts[-1]

            if mod_prefix in imports:
                target_file, _ = imports[mod_prefix]
                if target_file and target_file in self.file_declarations:
                    if member_name in self.file_declarations[target_file]:
                        decl = self.file_declarations[target_file][member_name]
                        return decl["node_id"], decl.get("parameters", [])
                if target_file:
                    target_id = f"{target_file}::{member_name}"
                    return target_id, []

        # Case 4: Search globally across all workspace declarations by function name
        for f_path, decls in self.file_declarations.items():
            if callee_text in decls:
                decl = decls[callee_text]
                return decl["node_id"], decl.get("parameters", [])

        # Case 5: External call
        external_id = f"external::{callee_text}"
        if external_id not in self.graph:
            self.graph.add_node(
                external_id,
                file_path="<external>",
                name=callee_text,
                qualified_name=callee_text,
                is_external=True,
                is_entry_point=False,
                start_line=0,
                end_line=0,
                parameters=[],
            )
        return external_id, []
