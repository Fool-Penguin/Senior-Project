"""
walker.py - Symbolic Taint Walker for CWE-89 (SQL Injection).

Traverses Data-Flow Graphs (DFG) across single-file and multi-file codebases,
tracking untrusted input from sources (request.args, req.query, etc.) through
string concatenations, formatting, and inter-procedural bindings to SQL execution sinks
(cursor.execute, db.query, etc.), detecting parameterized query sanitization.
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import networkx as nx

from ..graphs.call_graph import CallGraphBuilder
from ..graphs.dfg import DFGBuilder
from ..models.contracts import CodeLocation, SymbolicFinding, TaintStep
from ..parser.cst_manager import CSTParserManager, LanguageType


class SymbolicTaintWalker:
    """
    Symbolic DFG traversal engine identifying CWE-89 SQL Injection vulnerabilities.
    """

    SOURCE_KEYWORDS = {
        "request.args",
        "req.args",
        "request.form",
        "req.form",
        "request.values",
        "request.json",
        "request.get_json",
        "request.get",
        "request.data",
        "request.post",
        "request.cookies",
        "req.query",
        "req.params",
        "req.body",
        "req.param",
        "req.headers",
        "searchparams",
        "search_term",
        "user_input",
        "username_input",
        "search",
    }

    SQL_METHOD_SINKS = {
        "execute",
        "executemany",
        "query",
        "raw",
        "rawquery",
        "$queryraw",
        "$queryrawunsafe",
        "$executeraw",
        "$executerawunsafe",
    }

    SQL_FUNCTION_SINKS = {
        "execute",
        "executemany",
        "query",
        "execute_query",
        "execute_filtered_query",
        "run_query",
        "raw_query",
    }

    NON_SINK_RECEIVERS = {
        "req",
        "request",
        "response",
        "res",
        "app",
        "router",
        "logger",
        "console",
    }

    SINK_PATTERNS = SQL_METHOD_SINKS | SQL_FUNCTION_SINKS

    def __init__(self) -> None:
        self.cst_manager = CSTParserManager.get_instance()

    def is_source_node(self, node_data: Dict[str, Any]) -> bool:
        """Determine if a DFG node represents untrusted user input."""
        expr = node_data.get("expression_text", "").lower()
        var = node_data.get("var_name", "").lower()

        # Check explicit keywords
        for kw in self.SOURCE_KEYWORDS:
            if kw in expr or kw in var:
                return True

        # Check route / handler parameter heuristic
        if node_data.get("node_kind") == "PARAM":
            if var in ("category", "search_term", "query", "user_id", "username", "id", "input_str", "term"):
                return True

        return False

    def is_sink_node(self, node_data: Dict[str, Any]) -> bool:
        """Determine if a DFG node represents an SQL execution sink."""
        if node_data.get("node_kind") != "CALL_ARG":
            return False

        fn_text = node_data.get("var_name", "").strip()
        if not fn_text:
            return False

        if "." in fn_text:
            parts = fn_text.split(".")
            receiver = parts[0].strip().lower()
            method = parts[-1].strip().lower()

            # Reject HTTP request/response receivers (e.g. req.query, request.args)
            if receiver in self.NON_SINK_RECEIVERS or any(
                receiver.startswith(f"{r}.") for r in ("req", "request")
            ):
                return False

            if method in self.SQL_METHOD_SINKS:
                return True
        else:
            fn_lower = fn_text.lower()
            if fn_lower in self.SQL_FUNCTION_SINKS:
                return True

        return False

    def is_sanitizer_operation(self, node_data: Dict[str, Any], edge_data: Dict[str, Any]) -> bool:
        """Check if an operation safely sanitizes or type-casts the tainted value."""
        expr = node_data.get("expression_text", "")
        # Type casting sanitization
        if re.search(r"\b(int|float|parseint|number)\s*\(", expr, re.IGNORECASE):
            return True
        return False

    def is_sink_parameterized(
        self, sink_node_data: Dict[str, Any], code_line: str
    ) -> bool:
        """
        Check if the SQL sink call uses parameterized query placeholders
        (e.g. (?, %s, $1, :param)) rather than direct string interpolation/concatenation.
        """
        line_clean = code_line.strip()

        # Non-driver utility function sinks never implement DB parameterization
        if "execute_filtered_query" in line_clean or sink_node_data.get("var_name") == "execute_filtered_query":
            return False

        # If line uses direct interpolation outside secondary parameter containers [...], (...), {...}, it's vulnerable
        outside_containers = re.sub(r",\s*\[[^\]]*\]", "", line_clean)
        outside_containers = re.sub(r",\s*\([^)]*\)", "", outside_containers)
        outside_containers = re.sub(r",\s*\{[^}]*\}", "", outside_containers)
        if "f\"" in outside_containers or "f'" in outside_containers or "${" in outside_containers:
            return False

        # If line contains direct concatenation (+) with SQL keywords outside containers
        if "+" in outside_containers and any(k in outside_containers.upper() for k in ["SELECT", "WHERE", "INSERT", "UPDATE", "DELETE", "FROM"]):
            return False

        # If line contains % formatting without secondary parameter container
        if "%" in line_clean and not re.search(r",\s*(?:\(|\[|\{|[a-zA-Z_][a-zA-Z0-9_]*)", line_clean):
            return False

        # Strip JavaScript/TypeScript callback functions before checking for parameter container
        cleaned = re.sub(r",\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>.*", "", line_clean, flags=re.DOTALL)
        cleaned = re.sub(r",\s*function\s*\(.*", "", cleaned, flags=re.DOTALL)

        # 1. Reject empty parameter containers: (), [], {}, tuple(), list(), dict(), None, null, undefined
        if re.search(
            r",\s*(?:\(\s*\)|\[\s*\]|\{\s*\}|tuple\s*\(\s*\)|list\s*\(\s*\)|dict\s*\(\s*\)|None|null|undefined)\s*(?:\)|,|$)",
            cleaned,
        ):
            return False

        # 2. Require non-empty container contents or parameter variable identifiers:
        # e.g. cursor.execute(query, (param1, param2)), db.query(sql, [param1]), cursor.execute(sql, {"user": user}),
        # or cursor.execute(query, params) / db.query(sql, values)
        if re.search(r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s]|[a-zA-Z_][a-zA-Z0-9_]*)", cleaned):
            return True

        return False

    def analyze_code(
        self,
        code: str,
        language: str = "python",
        file_path: str = "snippet.py",
    ) -> List[SymbolicFinding]:
        """
        Analyze a single code snippet or file and return detected CWE-89 SymbolicFindings.
        """
        norm_path = os.path.normpath(os.path.abspath(file_path)) if file_path else "snippet.py"
        dfg_builder = DFGBuilder()
        dfg = dfg_builder.build_for_code(code, language=language, file_path=norm_path)

        file_sources = {norm_path: code}
        return self._find_taint_paths_in_dfg(dfg, file_sources)

    def analyze_workspace(self, directory: str) -> List[SymbolicFinding]:
        """
        Analyze an entire workspace directory with cross-file Call Graph and inter-procedural DFG.
        """
        cg_builder = CallGraphBuilder()
        cg_builder.add_workspace(directory)
        call_graph = cg_builder.build()

        dfg_builder = DFGBuilder(call_graph_builder=cg_builder)
        for f_path, f_code in cg_builder.file_sources.items():
            f_lang = cg_builder.file_languages.get(f_path, "python")
            dfg_builder.build_for_code(f_code, language=f_lang, file_path=f_path)

        dfg_builder.link_inter_procedural_calls(call_graph)
        return self._find_taint_paths_in_dfg(dfg_builder.graph, cg_builder.file_sources)

    def analyze_files(self, file_paths: List[str]) -> List[SymbolicFinding]:
        """
        Analyze a specific collection of files (e.g. cross-file demo pair).
        """
        cg_builder = CallGraphBuilder()
        for fp in file_paths:
            cg_builder.add_file(fp)
        call_graph = cg_builder.build()

        dfg_builder = DFGBuilder(call_graph_builder=cg_builder)
        for f_path, f_code in cg_builder.file_sources.items():
            f_lang = cg_builder.file_languages.get(f_path, "python")
            dfg_builder.build_for_code(f_code, language=f_lang, file_path=f_path)

        dfg_builder.link_inter_procedural_calls(call_graph)
        return self._find_taint_paths_in_dfg(dfg_builder.graph, cg_builder.file_sources)

    def walk(
        self,
        code: str,
        language: str = "python",
        file_path: str = "snippet.py",
    ) -> List[SymbolicFinding]:
        """
        Alias for analyze_code providing explicit walk() interface for Stage 3A traversal.
        """
        return self.analyze_code(code, language=language, file_path=file_path)

    def _find_taint_paths_in_dfg(
        self, dfg: nx.DiGraph, file_sources: Dict[str, str]
    ) -> List[SymbolicFinding]:
        """
        Traverse DFG using forward reachability from source nodes to sink nodes.
        """
        findings: List[SymbolicFinding] = []
        source_nodes = [n for n, d in dfg.nodes(data=True) if self.is_source_node(d)]
        sink_nodes = [n for n, d in dfg.nodes(data=True) if self.is_sink_node(d)]

        # If no explicit source node was flagged by heuristics, look for parameters in functions that feed sinks
        if not source_nodes:
            source_nodes = [
                n for n, d in dfg.nodes(data=True)
                if d.get("node_kind") == "PARAM"
            ]

        visited_paths: Set[Tuple[str, str]] = set()

        for src in source_nodes:
            src_data = dfg.nodes[src]
            src_file = src_data.get("file_path", "")

            for snk in sink_nodes:
                if src == snk:
                    continue
                snk_data = dfg.nodes[snk]
                snk_file = snk_data.get("file_path", "")

                pair_key = (src, snk)
                if pair_key in visited_paths:
                    continue

                if nx.has_path(dfg, src, snk):
                    visited_paths.add(pair_key)

                    # Extract line content and full call expression for sink
                    snk_line_num = snk_data.get("line_number", 1)
                    snk_code = file_sources.get(snk_file, "")
                    snk_lines = snk_code.splitlines()
                    snk_line_text = (
                        snk_lines[snk_line_num - 1]
                        if 0 < snk_line_num <= len(snk_lines)
                        else snk_data.get("expression_text", "")
                    )
                    snk_call_text = snk_data.get("expression_text") or snk_line_text

                    # 1. Specifically check the path reaching the query argument (arg 0)
                    # In SQL sink calls (execute, query, etc.), arg 0 is the SQL query statement.
                    # If untrusted input flows into arg 0 (via string concatenation, f-string,
                    # template literal, or % format), passing secondary parameters in arg 1
                    # cannot sanitize the injection.
                    snk_fn_name = snk_data.get("var_name", "")
                    is_helper_sink = snk_fn_name in ("execute_filtered_query", "execute_query", "run_query", "raw_query")
                    allowed_query_ops = (
                        ("arg_0", "arg_1", "arg_2", "kwarg_query", "kwarg_sql", "kwarg_operation", "kwarg_stmt", "kwarg_statement", "kwarg_filter", "kwarg_clause")
                        if is_helper_sink
                        else ("arg_0", "kwarg_query", "kwarg_sql", "kwarg_operation", "kwarg_stmt", "kwarg_statement")
                    )
                    query_arg_preds = [
                        pred for pred in dfg.predecessors(snk)
                        if dfg.get_edge_data(pred, snk, default={}).get("operation") in allowed_query_ops
                    ]

                    raw_path = None
                    has_unparameterized_string_format = False

                    # Check reachable query argument predecessors
                    for q_pred in query_arg_preds:
                        if nx.has_path(dfg, src, q_pred):
                            cand_path = nx.shortest_path(dfg, src, q_pred) + [snk]
                            cand_has_formatting = False
                            for i in range(len(cand_path) - 1):
                                u_node = cand_path[i]
                                v_node = cand_path[i + 1]
                                u_data = dfg.nodes[u_node]
                                e_data = dfg.get_edge_data(u_node, v_node, default={})
                                flow_type = e_data.get("flow_type", "")

                                if flow_type in ("STRING_CONCAT", "FORMAT_INTERPOLATION"):
                                    cand_has_formatting = True
                                    break
                                if u_data.get("node_kind") == "INTERPOLATION":
                                    cand_has_formatting = True
                                    break
                                if u_data.get("node_kind") == "BINARY_OP" and any(
                                    op in u_data.get("expression_text", "") for op in ("+", "%")
                                ):
                                    cand_has_formatting = True
                                    break
                                if (
                                    u_data.get("node_kind") == "CALL_ARG"
                                    and u_data.get("var_name", "").endswith(".format")
                                ):
                                    cand_has_formatting = True
                                    break

                            if cand_has_formatting:
                                raw_path = cand_path
                                has_unparameterized_string_format = True
                                break
                            elif raw_path is None:
                                raw_path = cand_path

                    # If no path reaching arg 0 was found (e.g. genuine parameterized query
                    # where tainted input only enters through parameter container arg 1),
                    # use shortest path to snk
                    if raw_path is None:
                        try:
                            raw_path = nx.shortest_path(dfg, src, snk)
                        except nx.NetworkXNoPath:
                            continue

                    # Check for sanitization via parameter container at sink using full call text
                    is_sanitized = self.is_sink_parameterized(snk_data, snk_call_text)

                    # Also verify if the selected raw_path reaching the sink contains unparameterized string formatting.
                    # This check only invalidates sanitization if the path reaches the query statement itself (arg 0).
                    # Formatting inside secondary parameter containers (e.g. ['%' + term + '%'] in arg 1) is safe.
                    is_reaching_query_arg = (
                        not query_arg_preds
                        or (len(raw_path) >= 2 and raw_path[-2] in query_arg_preds)
                    )
                    if not has_unparameterized_string_format and is_reaching_query_arg:
                        for i in range(len(raw_path) - 1):
                            u_node = raw_path[i]
                            v_node = raw_path[i + 1]
                            u_data = dfg.nodes[u_node]
                            e_data = dfg.get_edge_data(u_node, v_node, default={})
                            flow_type = e_data.get("flow_type", "")

                            if flow_type in ("STRING_CONCAT", "FORMAT_INTERPOLATION"):
                                has_unparameterized_string_format = True
                                break
                            if u_data.get("node_kind") == "INTERPOLATION":
                                has_unparameterized_string_format = True
                                break
                            if u_data.get("node_kind") == "BINARY_OP" and any(
                                op in u_data.get("expression_text", "") for op in ("+", "%")
                            ):
                                has_unparameterized_string_format = True
                                break
                            if (
                                u_data.get("node_kind") == "CALL_ARG"
                                and u_data.get("var_name", "").endswith(".format")
                            ):
                                has_unparameterized_string_format = True
                                break

                    # If the query itself was constructed using unparameterized string formatting,
                    # passing secondary dummy parameters cannot sanitize it.
                    if has_unparameterized_string_format:
                        is_sanitized = False

                    # Check for explicit sanitizer operations along the path (e.g. int(), float(), parseInt())
                    # Explicit type casts override since they guarantee safety even if formatted into an f-string
                    for n_step in raw_path:
                        n_data = dfg.nodes[n_step]
                        if self.is_sanitizer_operation(n_data, {}):
                            is_sanitized = True
                            break

                    # Build structured TaintSteps
                    taint_steps: List[Dict[str, Any]] = []
                    for idx, n_id in enumerate(raw_path, start=1):
                        curr_node = dfg.nodes[n_id]
                        curr_file = curr_node.get("file_path", "")
                        curr_line = curr_node.get("line_number", 1)
                        curr_code = file_sources.get(curr_file, "")
                        curr_lines = curr_code.splitlines()
                        snippet = (
                            curr_lines[curr_line - 1].strip()
                            if 0 < curr_line <= len(curr_lines)
                            else curr_node.get("expression_text", "")
                        )

                        op = curr_node.get("node_kind", "propagation")
                        if idx == 1:
                            op = "taint_source"
                        elif idx == len(raw_path):
                            op = "sql_sink"

                        taint_steps.append({
                            "step_index": idx,
                            "file": curr_file,
                            "line": curr_line,
                            "symbol": curr_node.get("var_name", ""),
                            "operation": op,
                            "code_snippet": snippet,
                        })

                    # Construct Source Node location
                    src_line_num = src_data.get("line_number", 1)
                    src_code = file_sources.get(src_file, "")
                    src_lines = src_code.splitlines()
                    src_snippet = (
                        src_lines[src_line_num - 1].strip()
                        if 0 < src_line_num <= len(src_lines)
                        else src_data.get("expression_text", "")
                    )

                    source_loc = {
                        "file": src_file,
                        "line": src_line_num,
                        "column": src_data.get("col_offset", 0),
                        "symbol": src_data.get("var_name", "user_input"),
                        "expression": src_snippet,
                    }

                    sink_loc = {
                        "file": snk_file,
                        "line": snk_line_num,
                        "column": snk_data.get("col_offset", 0),
                        "symbol": snk_data.get("var_name", "SQL Sink"),
                        "expression": snk_call_text.strip(),
                    }

                    finding = SymbolicFinding(
                        cwe_id="CWE-89",
                        cwe_name="Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')",
                        severity="CRITICAL" if not is_sanitized else "LOW",
                        source_node=source_loc,
                        sink_node=sink_loc,
                        taint_path=taint_steps,
                        sanitized=is_sanitized,
                        symbolic_confidence=0.95 if not is_sanitized else 0.20,
                        code_slice=snk_code or src_code,
                    )
                    findings.append(finding)

        # Fallback AST query check if DFG path didn't connect due to simplified script structure
        if not findings:
            findings = self._fallback_ast_sink_scan(file_sources)

        return findings

    def _fallback_ast_sink_scan(
        self, file_sources: Dict[str, str]
    ) -> List[SymbolicFinding]:
        """
        Safety fallback scanning AST directly for vulnerable sink concatenations.
        """
        findings: List[SymbolicFinding] = []
        sink_call_patterns = [
            ".execute(",
            ".executemany(",
            ".query(",
            ".raw(",
            ".rawquery(",
            ".$queryraw(",
            ".$queryrawunsafe(",
            ".$executeraw(",
            ".$executerawunsafe(",
            "execute_filtered_query(",
            "execute_query(",
            "run_query(",
        ]
        excluded_receivers = ["req.", "request.", "console.", "logger."]

        for file_path, code in file_sources.items():
            lines = code.splitlines()
            for idx, line in enumerate(lines, start=1):
                clean = line.strip()
                if not clean or clean.startswith(("#", "//", "/*")):
                    continue

                clean_lower = clean.lower()

                # Must be an actual database sink invocation, NOT a variable declaration or assignment
                is_sink_call = any(pat in clean_lower for pat in sink_call_patterns)
                if not is_sink_call:
                    continue

                # Exclude HTTP request receivers
                if any(ex in clean_lower for ex in excluded_receivers):
                    continue

                has_sql = any(k in clean.upper() for k in ["SELECT", "INSERT", "UPDATE", "DELETE", "WHERE", "FROM"])
                has_concat = (
                    "f\"" in clean
                    or "f'" in clean
                    or ("+" in clean and has_sql)
                    or ("%" in clean and has_sql)
                    or ("${" in clean and has_sql)
                )

                if has_concat:
                    is_sanitized = self.is_sink_parameterized({}, clean)
                    sym = "untrusted_input"
                    m = re.search(r"\{([a-zA-Z0-9_]+)\}|\$\{([a-zA-Z0-9_]+)\}|\+\s*([a-zA-Z0-9_]+)", clean)
                    if m:
                        sym = next(s for s in m.groups() if s)

                    # Look backwards strictly for actual untrusted sources
                    src_line_idx = None
                    if any(kw in clean_lower for kw in ["request", "req", "params", "args", "user_input", "search", "category"]):
                        src_line_idx = idx
                    else:
                        for b_i in range(idx - 2, max(-1, idx - 16), -1):
                            b_l = lines[b_i]
                            if any(kw in b_l.lower() for kw in ["request", "req", "params", "args", "user_input", "search", "category"]):
                                src_line_idx = b_i + 1
                                break

                    # If no untrusted source keyword was found in scope, do NOT flag safe code
                    if src_line_idx is None:
                        continue

                    source_loc = {
                        "file": file_path,
                        "line": src_line_idx,
                        "column": 0,
                        "symbol": sym,
                        "expression": lines[src_line_idx - 1].strip(),
                    }

                    sink_loc = {
                        "file": file_path,
                        "line": idx,
                        "column": 0,
                        "symbol": "SQL Sink",
                        "expression": clean,
                    }

                    taint_path = [
                        {
                            "step_index": 1,
                            "file": file_path,
                            "line": src_line_idx,
                            "symbol": sym,
                            "operation": "taint_source",
                            "code_snippet": lines[src_line_idx - 1].strip(),
                        },
                        {
                            "step_index": 2,
                            "file": file_path,
                            "line": idx,
                            "symbol": sym,
                            "operation": "sql_sink",
                            "code_snippet": clean,
                        },
                    ]

                    findings.append(
                        SymbolicFinding(
                            cwe_id="CWE-89",
                            cwe_name="Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')",
                            severity="CRITICAL" if not is_sanitized else "LOW",
                            source_node=source_loc,
                            sink_node=sink_loc,
                            taint_path=taint_path,
                            sanitized=is_sanitized,
                            symbolic_confidence=0.95 if not is_sanitized else 0.20,
                            code_slice=code,
                        )
                    )

        return findings
