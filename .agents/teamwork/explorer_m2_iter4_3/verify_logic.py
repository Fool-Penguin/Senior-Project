import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import networkx as nx

# Add codedee_server to path
SERVER_ROOT = Path(r"d:\4th-year\Senior-Project\codedee\codedee_server")
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.taint.walker import SymbolicTaintWalker
from app.models.contracts import SymbolicFinding

def patched_is_sink_parameterized(self, sink_node_data: Dict[str, Any], code_line: str) -> bool:
    line_clean = code_line.strip()
    if 'f"' in line_clean or "f'" in line_clean or "${" in line_clean:
        return False
    if "+" in line_clean and any(k in line_clean.upper() for k in ["SELECT", "WHERE", "INSERT", "UPDATE", "DELETE"]):
        return False
    if "%" in line_clean and not re.search(r",\s*(?:\(|\[|\{|[a-zA-Z_][a-zA-Z0-9_]*)", line_clean):
        return False
    cleaned = re.sub(r",\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>.*", "", line_clean, flags=re.DOTALL)
    cleaned = re.sub(r",\s*function\s*\(.*", "", cleaned, flags=re.DOTALL)
    if re.search(
        r",\s*(?:\(\s*\)|\[\s*\]|\{\s*\}|tuple\s*\(\s*\)|list\s*\(\s*\)|dict\s*\(\s*\)|None|null|undefined)\s*(?:\)|,|$)",
        cleaned,
    ):
        return False
    if re.search(r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s]|[a-zA-Z_][a-zA-Z0-9_]*)", cleaned):
        return True
    return False

def patched_find_taint_paths_in_dfg(self, dfg: nx.DiGraph, file_sources: Dict[str, str]) -> List[SymbolicFinding]:
    findings: List[SymbolicFinding] = []
    source_nodes = [n for n, d in dfg.nodes(data=True) if self.is_source_node(d)]
    sink_nodes = [n for n, d in dfg.nodes(data=True) if self.is_sink_node(d)]

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

                # 1. Specifically check path reaching the query argument (arg 0)
                # In SQL sink calls, arg 0 is the SQL query statement.
                # If untrusted input flows into arg 0, secondary parameters in arg 1 cannot sanitize it.
                query_arg_preds = [
                    pred for pred in dfg.predecessors(snk)
                    if dfg.get_edge_data(pred, snk, default={}).get("operation") in (
                        "arg_0", "kwarg_query", "kwarg_sql", "kwarg_operation", "kwarg_stmt", "kwarg_statement"
                    )
                ]

                raw_path = None
                has_unparameterized_string_format = False

                for q_pred in query_arg_preds:
                    if nx.has_path(dfg, src, q_pred):
                        cand_path = nx.shortest_path(dfg, src, q_pred) + [snk]
                        is_unparam = False
                        for i in range(len(cand_path) - 1):
                            u_node = cand_path[i]
                            v_node = cand_path[i + 1]
                            u_data = dfg.nodes[u_node]
                            e_data = dfg.get_edge_data(u_node, v_node, default={})
                            flow_type = e_data.get("flow_type", "")

                            if flow_type in ("STRING_CONCAT", "FORMAT_INTERPOLATION"):
                                is_unparam = True
                                break
                            if u_data.get("node_kind") == "INTERPOLATION":
                                is_unparam = True
                                break
                            if u_data.get("node_kind") == "BINARY_OP" and any(
                                op in u_data.get("expression_text", "") for op in ("+", "%")
                            ):
                                is_unparam = True
                                break
                            if (
                                u_data.get("node_kind") == "CALL_ARG"
                                and u_data.get("var_name", "").endswith(".format")
                            ):
                                is_unparam = True
                                break

                        if is_unparam:
                            raw_path = cand_path
                            has_unparameterized_string_format = True
                            break
                        elif raw_path is None:
                            raw_path = cand_path

                if raw_path is None:
                    try:
                        raw_path = nx.shortest_path(dfg, src, snk)
                    except nx.NetworkXNoPath:
                        continue

                # Check for sanitization via parameter container at sink
                is_sanitized = self.is_sink_parameterized(snk_data, snk_call_text)

                # Verify if the chosen path contains unparameterized string formatting
                if not has_unparameterized_string_format:
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

                if has_unparameterized_string_format:
                    is_sanitized = False

                # Check for explicit sanitizer operations along the path
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

    if not findings:
        findings = self._fallback_ast_sink_scan(file_sources)

    return findings

# Monkeypatch
SymbolicTaintWalker.is_sink_parameterized = patched_is_sink_parameterized
SymbolicTaintWalker._find_taint_paths_in_dfg = patched_find_taint_paths_in_dfg

def run_tests():
    walker = SymbolicTaintWalker()

    print("--- 1. Testing Shortest-Path Parameterization Bypass (Challenger 2 Defect 1) ---")
    # 1A Python concat + dummy param
    code_1a = """
    def search_account():
        user = request.args.get('user')
        sql = "SELECT * FROM users WHERE name = '" + user + "'"
        cursor.execute(sql, (user,))
    """
    f_1a = walker.analyze_code(code_1a, "python", "py_concat.py")
    vuln_1a = [f for f in f_1a if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vuln_1a) >= 1, f"Defect 1A failed: {f_1a}"
    print("Defect 1A (Python concat + (user,)) PASSED -> flagged CRITICAL")

    # 1B Python f-string + dummy param
    code_1b = """
    def search_account_fstr():
        user = request.args.get('user')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql, (user,))
    """
    f_1b = walker.analyze_code(code_1b, "python", "py_fstr.py")
    vuln_1b = [f for f in f_1b if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vuln_1b) >= 1, f"Defect 1B failed: {f_1b}"
    print("Defect 1B (Python f-string + (user,)) PASSED -> flagged CRITICAL")

    # 1C TS concat + dummy param
    code_1c = """
    export function getConcatenated(req: any) {
        const id = req.query.id;
        const sql = "SELECT * FROM users WHERE id = " + id;
        client.query(sql, [id]);
    }
    """
    f_1c = walker.analyze_code(code_1c, "typescript", "ts_concat.ts")
    vuln_1c = [f for f in f_1c if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vuln_1c) >= 1, f"Defect 1C failed: {f_1c}"
    print("Defect 1C (TS concat + [id]) PASSED -> flagged CRITICAL")

    # 1D JS concat + dummy param
    code_1d = """
    function getTaggedItems(req) {
        const tag = req.query.tag;
        const query = "SELECT * FROM items WHERE tag = '" + tag + "'";
        pool.query(query, [tag]);
    }
    """
    f_1d = walker.analyze_code(code_1d, "javascript", "js_concat.js")
    vuln_1d = [f for f in f_1d if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vuln_1d) >= 1, f"Defect 1D failed: {f_1d}"
    print("Defect 1D (JS concat + [tag]) PASSED -> flagged CRITICAL")

    print("\n--- 2. Testing Multi-Line Sink Call Truncation (Reviewer 2 Defect 1) ---")
    code_ml = """
    from flask import request
    def handler():
        user = request.args.get("user")
        cursor.execute(
            "SELECT * FROM users WHERE name = %s",
            (user,)
        )
    """
    f_ml = walker.analyze_code(code_ml, "python", "multi_line.py")
    assert len(f_ml) >= 1
    assert all(f.sanitized is True and f.severity == "LOW" for f in f_ml), f"Multi-line failed: {f_ml}"
    print("Multi-line sink call PASSED -> sanitized=True, severity=LOW")

    print("\n--- 3. Testing Parameter Variables (Reviewer 2 Defect 2) ---")
    code_var = """
    from flask import request
    def handler():
        user = request.args.get("user")
        query = "SELECT * FROM users WHERE name = %s"
        params = (user,)
        cursor.execute(query, params)
    """
    f_var = walker.analyze_code(code_var, "python", "var_params.py")
    assert len(f_var) >= 1
    assert all(f.sanitized is True and f.severity == "LOW" for f in f_var), f"Parameter variable failed: {f_var}"
    print("Parameter variable PASSED -> sanitized=True, severity=LOW")

    print("\n--- 4. Testing PEP 249 Dictionary Syntax (Reviewer 2 Defect 2 & Challenger 1 Defect B) ---")
    code_dict_inline = """
    from flask import request
    def handler():
        user = request.args.get("user")
        cursor.execute("SELECT * FROM users WHERE name = %(name)s", {"name": user})
    """
    f_di = walker.analyze_code(code_dict_inline, "python", "dict_inline.py")
    assert len(f_di) >= 1
    assert all(f.sanitized is True and f.severity == "LOW" for f in f_di), f"PEP 249 inline dict failed: {f_di}"
    print("PEP 249 inline dict PASSED -> sanitized=True, severity=LOW")

    code_dict_var = """
    from flask import request
    def handler():
        user = request.args.get("user")
        query = "SELECT * FROM users WHERE name = %(name)s"
        params = {"name": user}
        cursor.execute(query, params)
    """
    f_dv = walker.analyze_code(code_dict_var, "python", "dict_var.py")
    assert len(f_dv) >= 1
    assert all(f.sanitized is True and f.severity == "LOW" for f in f_dv), f"PEP 249 var dict failed: {f_dv}"
    print("PEP 249 var dict PASSED -> sanitized=True, severity=LOW")

    print("\n--- 5. Testing Existing Legitimate & Adversarial Protections ---")
    # Empty tuple bypass rejected
    code_empty = """
    def evasion():
        user = request.args.get('user')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql, ())
    """
    f_emp = walker.analyze_code(code_empty, "python", "empty.py")
    assert any(f.severity == "CRITICAL" and not f.sanitized for f in f_emp)
    print("Empty tuple rejection PASSED -> CRITICAL")

    # None parameter rejected
    code_none = """
    def evasion_none():
        user = request.args.get('user')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql, None)
    """
    f_none = walker.analyze_code(code_none, "python", "none.py")
    assert any(f.severity == "CRITICAL" and not f.sanitized for f in f_none)
    print("None parameter rejection PASSED -> CRITICAL")

    # Safe type cast
    code_cast = """
    def get_by_id():
        raw_id = request.args.get('id')
        user_id = int(raw_id)
        cursor.execute(f"SELECT * FROM items WHERE id = {user_id}")
    """
    f_cast = walker.analyze_code(code_cast, "python", "cast.py")
    assert all(f.sanitized is True and f.severity == "LOW" for f in f_cast)
    print("Safe int() cast PASSED -> LOW")

    # Static query no findings
    code_static = """
    def list_users():
        cursor.execute("SELECT * FROM users")
    """
    f_stat = walker.analyze_code(code_static, "python", "static.py")
    assert len(f_stat) == 0
    print("Static query PASSED -> 0 findings")

    print("\n==============================================")
    print("ALL VERIFICATION SUITE CHECKS PASSED 100%!")
    print("==============================================")

if __name__ == "__main__":
    run_tests()
