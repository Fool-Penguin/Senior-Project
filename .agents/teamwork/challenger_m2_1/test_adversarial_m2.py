"""
test_adversarial_m2.py - Comprehensive Adversarial Stress-Test Suite for Milestone 2.

Empirical Challenger verification for:
1. Deeply nested or circular call graphs (intra/cross-file mutual recursion, cycles, scaling limits).
2. Complex control-flow structures (nested try-catch-finally, switch/match, complex loops).
3. Obfuscated or complex DFG chains (aliasing, reassignments, unpacks, container blindness, sink heuristics).
4. Malformed / syntax-error source files (Tree-sitter ERROR nodes, token soup, null bytes).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import networkx as nx
import pytest

from codedee.codedee_server.app.parser.cst_manager import CSTParserManager, LanguageType
from codedee.codedee_server.app.graphs.call_graph import CallGraphBuilder
from codedee.codedee_server.app.graphs.cfg import CFGBuilder
from codedee.codedee_server.app.graphs.dfg import DFGBuilder
from codedee.codedee_server.app.maintainability.engine import MaintainabilityEngine
from codedee.codedee_server.app.taint.walker import SymbolicTaintWalker


# ============================================================================
# Category 1: Deeply Nested and Circular Call Graphs
# ============================================================================

class TestAdversarialCallGraphs:
    """Stress-tests for circular, deeply nested, and recursive call graphs."""

    def test_intra_file_mutual_recursion(self):
        """Mutually recursive functions in a single Python file."""
        code = """
def ping(n, data):
    if n <= 0:
        return data
    return pong(n - 1, data)

def pong(n, data):
    if n <= 0:
        return data
    return ping(n - 1, data)
"""
        builder = CallGraphBuilder()
        builder.add_file("mutual_rec.py", code=code, language="python")
        graph = builder.build()

        ping_id = "mutual_rec.py::ping"
        pong_id = "mutual_rec.py::pong"

        assert ping_id in graph.nodes
        assert pong_id in graph.nodes
        assert graph.has_edge(ping_id, pong_id), "ping should call pong"
        assert graph.has_edge(pong_id, ping_id), "pong should call ping"

        cycles = list(nx.simple_cycles(graph))
        assert len(cycles) == 1
        assert set(cycles[0]) == {ping_id, pong_id}

    def test_cross_file_mutual_recursion(self):
        """Cross-file mutual recursion between mod_a.py and mod_b.py."""
        code_a = """
from mod_b import func_b

def func_a(x):
    if x > 0:
        return func_b(x - 1)
    return x
"""
        code_b = """
from mod_a import func_a

def func_b(y):
    if y > 0:
        return func_a(y - 1)
    return y
"""
        temp_dir = tempfile.mkdtemp(prefix="codedee_adv_call_")
        try:
            path_a = os.path.join(temp_dir, "mod_a.py")
            path_b = os.path.join(temp_dir, "mod_b.py")

            with open(path_a, "w", encoding="utf-8") as f:
                f.write(code_a)
            with open(path_b, "w", encoding="utf-8") as f:
                f.write(code_b)

            builder = CallGraphBuilder()
            builder.add_file(path_a)
            builder.add_file(path_b)
            graph = builder.build()

            norm_a = path_a.replace("\\", "/") + "::func_a"
            norm_b = path_b.replace("\\", "/") + "::func_b"

            assert norm_a in graph.nodes
            assert norm_b in graph.nodes
            assert graph.has_edge(norm_a, norm_b), "func_a must call func_b across files"
            assert graph.has_edge(norm_b, norm_a), "func_b must call func_a across files"

            cycles = list(nx.simple_cycles(graph))
            assert len(cycles) >= 1
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_call_chain_scaling_within_safe_boundary(self):
        """Linear call chain scaling up to 50 functions fn_0 -> fn_1 -> ... -> fn_49."""
        N = 50
        lines = [f"def fn_{i}(x):\n    return fn_{i+1}(x + 1)\n" for i in range(N - 1)]
        lines.append(f"def fn_{N-1}(x):\n    return x\n")
        code = "\n".join(lines)

        builder = CallGraphBuilder()
        builder.add_file("chain_50.py", code=code, language="python")
        graph = builder.build()

        assert len(graph.nodes) >= N
        path = nx.shortest_path(graph, f"chain_50.py::fn_0", f"chain_50.py::fn_{N-1}")
        assert len(path) == N

    def test_reproduce_cst_text_lifetime_access_violation_at_scale(self):
        """
        Adversarial Bug Reproduction:
        When a source file exceeds ~87 functions (e.g. 100 functions),
        CallGraphBuilder.add_file() crashes with Windows fatal exception: access violation
        due to temporary source_bytes garbage collection in CSTParserManager.parse().
        Verified in a separate subprocess to prevent aborting the entire pytest runner.
        """
        script = """
import sys
sys.path.insert(0, '.')
from codedee.codedee_server.app.graphs.call_graph import CallGraphBuilder

N = 100
lines = [f'def fn_{i}(x):\\n    return fn_{i+1}(x + 1)\\n' for i in range(N - 1)]
lines.append(f'def fn_{N-1}(x):\\n    return x\\n')
code = '\\n'.join(lines)

b = CallGraphBuilder()
b.add_file('crash_repro.py', code=code, language='python')
b.build()
print('SUCCESS_UNEXPECTED')
"""
        proc = subprocess.run(
            [sys.executable, "-X", "faulthandler", "-c", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        # Empirical finding: subprocess crashes with access violation (exit code != 0)
        assert proc.returncode != 0, "Expected crash/failure on N=100 due to buffer GC access violation"
        assert "access violation" in proc.stderr.lower() or proc.returncode != 0

    def test_long_circular_cycle_50_functions(self):
        """A 50-function circular loop: fn_0 -> fn_1 -> ... -> fn_49 -> fn_0."""
        lines = [f"def fn_{i}(x):\n    return fn_{i+1}(x)\n" for i in range(49)]
        lines.append("def fn_49(x):\n    return fn_0(x)\n")
        code = "\n".join(lines)

        builder = CallGraphBuilder()
        builder.add_file("cycle_50.py", code=code, language="python")
        graph = builder.build()

        cycles = list(nx.simple_cycles(graph))
        assert len(cycles) == 1
        assert len(cycles[0]) == 50

    def test_direct_self_recursion(self):
        """Self-recursive function creating a self-loop edge."""
        code_py = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
        builder = CallGraphBuilder()
        builder.add_file("factorial.py", code=code_py, language="python")
        graph = builder.build()

        fn_id = "factorial.py::factorial"
        assert graph.has_edge(fn_id, fn_id), "Self-recursion should create a self-loop edge"

    def test_javascript_circular_commonjs_and_es6(self):
        """Circular references in JavaScript using CommonJS require syntax."""
        code_js_a = """
const b = require('./serviceB');
function serviceA(input) {
    return b.serviceB(input);
}
module.exports = { serviceA };
"""
        code_js_b = """
const a = require('./serviceA');
function serviceB(input) {
    if (input.length > 10) {
        return a.serviceA(input.slice(1));
    }
    return input;
}
module.exports = { serviceB };
"""
        temp_dir = tempfile.mkdtemp(prefix="codedee_adv_js_")
        try:
            path_a = os.path.join(temp_dir, "serviceA.js")
            path_b = os.path.join(temp_dir, "serviceB.js")
            with open(path_a, "w", encoding="utf-8") as f:
                f.write(code_js_a)
            with open(path_b, "w", encoding="utf-8") as f:
                f.write(code_js_b)

            builder = CallGraphBuilder()
            builder.add_file(path_a)
            builder.add_file(path_b)
            graph = builder.build()

            norm_a = path_a.replace("\\", "/") + "::serviceA"
            norm_b = path_b.replace("\\", "/") + "::serviceB"

            assert norm_a in graph.nodes
            assert norm_b in graph.nodes
            assert graph.has_edge(norm_a, norm_b)
            assert graph.has_edge(norm_b, norm_a)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_taint_propagation_through_mutual_recursion(self):
        """Taint walker must traverse mutually recursive calls without infinite looping."""
        code = """
import sqlite3

def ping_handler(request):
    raw_input = request.args.get('search')
    return pong_helper(raw_input, 3)

def pong_helper(data, countdown):
    if countdown <= 0:
        conn = sqlite3.connect("app.db")
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM items WHERE query = '{data}'")
        return cur.fetchall()
    return ping_helper(data, countdown - 1)

def ping_helper(data, countdown):
    return pong_helper(data, countdown)
"""
        walker = SymbolicTaintWalker()
        findings = walker.analyze_code(code, language="python", file_path="mutual_taint.py")
        assert len(findings) >= 1
        finding = findings[0]
        assert finding.cwe_id == "CWE-89"
        assert finding.severity == "CRITICAL"
        assert not finding.sanitized
        assert len(finding.taint_path) >= 2


# ============================================================================
# Category 2: Complex Control-Flow Structures
# ============================================================================

class TestAdversarialControlFlow:
    """Stress-tests for deeply nested try-catch-finally, switch/match, and loops."""

    def test_nested_try_catch_finally_python(self):
        """Triple-nested try/except/finally in Python with returns inside multiple blocks."""
        code = """
def robust_pipeline(val):
    try:
        step1 = val + 1
        try:
            step2 = step1 / 2
            try:
                step3 = step2 * 3
                return step3
            except ZeroDivisionError:
                return -1
            finally:
                cleanup_inner()
        except TypeError as te:
            step2 = 0
        finally:
            cleanup_mid()
    except Exception as e:
        return 0
    finally:
        cleanup_outer()
    return step1
"""
        builder = CFGBuilder()
        cfgs = builder.build_for_code(code, language="python", file_path="robust.py")
        assert "robust_pipeline" in cfgs
        cfg = cfgs["robust_pipeline"]

        assert "robust.py::robust_pipeline::ENTRY" in cfg.nodes
        assert "robust.py::robust_pipeline::EXIT" in cfg.nodes

        edge_types = {d.get("edge_type") for _, _, d in cfg.edges(data=True)}
        assert "EXCEPTION_EDGE" in edge_types
        assert "FALLTHROUGH" in edge_types
        assert nx.has_path(cfg, "robust.py::robust_pipeline::ENTRY", "robust.py::robust_pipeline::EXIT")

    def test_nested_try_catch_finally_javascript(self):
        """Nested try-catch-finally in JavaScript with empty blocks."""
        code = """
function processData(input) {
    let result = null;
    try {
        try {
            result = JSON.parse(input);
        } catch (innerErr) {
            // empty catch
        } finally {
            // empty finally
        }
    } catch (outerErr) {
        result = {};
    } finally {
        console.log("done");
    }
    return result;
}
"""
        builder = CFGBuilder()
        cfgs = builder.build_for_code(code, language="javascript", file_path="proc.js")
        assert "processData" in cfgs
        cfg = cfgs["processData"]
        assert nx.has_path(cfg, "proc.js::processData::ENTRY", "proc.js::processData::EXIT")

    def test_python_match_case_statements_defect_reproduction(self):
        """
        Adversarial Defect Reproduction:
        In engine.py, decision_types looks for 'match_clause', but Tree-sitter
        produces 'case_clause'. As a result, Cyclomatic Complexity fails to count
        match case branches, yielding CC=1 instead of 1 + 4 = 5.
        """
        code = """
def dispatch_command(cmd, payload):
    match cmd:
        case "create" if payload is not None:
            res = do_create(payload)
        case "update":
            res = do_update(payload)
        case "delete":
            res = do_delete(payload)
        case _:
            res = default_action()
    return res
"""
        cfg_builder = CFGBuilder()
        cfgs = cfg_builder.build_for_code(code, language="python", file_path="dispatch.py")
        assert "dispatch_command" in cfgs

        engine = MaintainabilityEngine()
        metrics = engine.analyze_code(code, language="python", file_path="dispatch.py")
        # Defect documentation: expected CC >= 4, actual CC is 1 because 'match_clause' != 'case_clause'
        cst = CSTParserManager.get_instance()
        tree = cst.parse(code, "python")
        case_clauses = cst.find_all_by_type(tree.root_node, ["case_clause"])
        assert len(case_clauses) == 4, "Tree-sitter node type is indeed case_clause"
        # Confirm that engine.py currently misses this:
        assert metrics.cyclomatic_complexity == 1, "Confirms CC bug: engine misses case_clause decision points"

    def test_javascript_nested_switch_fallthrough(self):
        """JavaScript nested switch statements with fall-through cases."""
        code = """
function parseToken(type, subType) {
    let tag = "unknown";
    switch (type) {
        case 1:
        case 2:
            switch (subType) {
                case 'a':
                    tag = "alpha";
                    break;
                case 'b':
                    tag = "beta";
                    break;
                default:
                    tag = "sub_default";
            }
            break;
        case 3:
            tag = "gamma";
            break;
        default:
            tag = "default";
    }
    return tag;
}
"""
        cfg_builder = CFGBuilder()
        cfgs = cfg_builder.build_for_code(code, language="javascript", file_path="switch.js")
        assert "parseToken" in cfgs
        cfg = cfgs["parseToken"]
        assert nx.has_path(cfg, "switch.js::parseToken::ENTRY", "switch.js::parseToken::EXIT")

        engine = MaintainabilityEngine()
        metrics = engine.analyze_code(code, language="javascript", file_path="switch.js")
        assert metrics.cyclomatic_complexity >= 4

    def test_complex_nested_loops_with_break_continue(self):
        """Nested loops with multiple breaks and continues in Python."""
        code = """
def matrix_search(matrix, target):
    found = False
    for r in range(len(matrix)):
        if r % 2 == 0:
            continue
        c = 0
        while c < len(matrix[r]):
            if matrix[r][c] == target:
                found = True
                break
            c += 1
        if found:
            break
    return found
"""
        builder = CFGBuilder()
        cfgs = builder.build_for_code(code, language="python", file_path="matrix.py")
        cfg = cfgs["matrix_search"]
        edge_types = {d.get("edge_type") for _, _, d in cfg.edges(data=True)}
        assert "LOOP_BODY" in edge_types
        assert nx.has_path(cfg, "matrix.py::matrix_search::ENTRY", "matrix.py::matrix_search::EXIT")

    def test_unreachable_dead_code_handling(self):
        """Unreachable statements following unconditional returns."""
        code = """
def dead_code_fn(x):
    return x
    y = x + 1
    return y
"""
        builder = CFGBuilder()
        cfgs = builder.build_for_code(code, language="python", file_path="dead.py")
        cfg = cfgs["dead_code_fn"]
        assert nx.has_path(cfg, "dead.py::dead_code_fn::ENTRY", "dead.py::dead_code_fn::EXIT")

    def test_empty_function_bodies(self):
        """Functions with empty bodies or only pass/ellipsis."""
        code = """
def empty_fn():
    pass

def ellipsis_fn():
    ...
"""
        builder = CFGBuilder()
        cfgs = builder.build_for_code(code, language="python", file_path="empty.py")
        assert "empty_fn" in cfgs
        assert "ellipsis_fn" in cfgs
        assert nx.has_path(cfgs["empty_fn"], "empty.py::empty_fn::ENTRY", "empty.py::empty_fn::EXIT")
        assert nx.has_path(cfgs["ellipsis_fn"], "empty.py::ellipsis_fn::ENTRY", "empty.py::ellipsis_fn::EXIT")


# ============================================================================
# Category 3: Obfuscated or Complex DFG Chains
# ============================================================================

class TestAdversarialDataFlowAndTaint:
    """Stress-tests for variable aliasing, reassignments, unpacks, and sinks."""

    def test_variable_reassignment_clean_overwrites_taint(self):
        """
        Reassignment of a tainted variable to a constant literal.
        """
        code = """
import sqlite3

def clean_reassignment(request):
    val = request.args.get('search')
    val = "safe_hardcoded_literal"
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM items WHERE name = '{val}'")
"""
        walker = SymbolicTaintWalker()
        findings = walker.analyze_code(code, language="python", file_path="reassign.py")
        assert isinstance(findings, list)

    def test_deep_aliasing_chain_taint_propagation(self):
        """Taint flows through 5 levels of variable aliasing: a -> b -> c -> d -> e -> sink."""
        code = """
import sqlite3

def aliasing_chain(request):
    a = request.args.get('data')
    b = a
    c = b
    d = c
    e = d
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE info = '" + e + "'")
"""
        walker = SymbolicTaintWalker()
        findings = walker.analyze_code(code, language="python", file_path="alias.py")
        assert len(findings) >= 1
        finding = findings[0]
        assert finding.cwe_id == "CWE-89"
        assert finding.severity == "CRITICAL"
        assert not finding.sanitized

    def test_divergent_branches_reassignment(self):
        """Taint flows through an if-branch assignment."""
        code = """
import sqlite3

def branch_taint(request, flag):
    untrusted = request.args.get('input')
    if flag:
        query_val = untrusted
    else:
        query_val = "fixed"
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM logs WHERE tag = '{query_val}'")
"""
        walker = SymbolicTaintWalker()
        findings = walker.analyze_code(code, language="python", file_path="branch.py")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"

    def test_python_tuple_and_dict_unpack_graceful(self):
        """Python tuple unpacking (a, b = ...) and dictionary unpacking without crashing."""
        code = """
def unpack_test(request):
    a, b = request.args.get('x'), 123
    data = {"user": a, "id": b}
    return data
"""
        dfg_builder = DFGBuilder()
        dfg = dfg_builder.build_for_code(code, language="python", file_path="unpack.py")
        assert len(dfg.nodes) >= 1

    def test_javascript_destructuring_graceful(self):
        """JavaScript object and array destructuring without crashing."""
        code = """
function handleRequest(req, res) {
    const { username, role } = req.body;
    const [firstParam, ...otherParams] = req.params;
    return { username, firstParam };
}
"""
        dfg_builder = DFGBuilder()
        dfg = dfg_builder.build_for_code(code, language="javascript", file_path="destruct.js")
        assert len(dfg.nodes) >= 1

    def test_nested_interpolations(self):
        """Nested string interpolations in Python f-strings."""
        code_py = """
import sqlite3
def nested_fstring(request):
    inner = request.args.get('name')
    query = f"SELECT * FROM users WHERE name = '{f'{inner}'}'"
    conn = sqlite3.connect("db.sqlite")
    conn.cursor().execute(query)
"""
        walker = SymbolicTaintWalker()
        findings = walker.analyze_code(code_py, language="python", file_path="nest_fstr.py")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"

    def test_chained_binary_string_concatenation(self):
        """Chained binary string concatenation tree."""
        code = """
import sqlite3
def big_concat(request):
    q1 = request.args.get('p1')
    q2 = request.args.get('p2')
    sql = "SELECT " + q1 + " FROM t1 " + " JOIN t2 ON " + q2 + " WHERE id = 1 " + " ORDER BY id"
    conn = sqlite3.connect("db.sqlite")
    conn.cursor().execute(sql)
"""
        walker = SymbolicTaintWalker()
        findings = walker.analyze_code(code, language="python", file_path="big_concat.py")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"

    def test_raw_sink_pattern_overreach_defect_reproduction(self):
        """
        Adversarial Defect Reproduction:
        In walker.py, 'raw' is included in SINK_PATTERNS and matched via 'pattern in var_lower'.
        Any variable named raw_id, raw_input, or raw_text is falsely identified as an SQL execution sink,
        causing a false finding at line 4 before the type casting occurs.
        """
        code = """
import sqlite3
def cast_func(request):
    raw_id = request.args.get('id')
    clean_id = int(raw_id)
    query = f"SELECT * FROM items WHERE id = {clean_id}"
    conn = sqlite3.connect("db.sqlite")
    conn.cursor().execute(query)
"""
        walker = SymbolicTaintWalker()
        # Verify that raw_id matches as sink due to "raw" in SINK_PATTERNS
        assert walker.is_sink_node({"expression_text": "raw_id", "var_name": "raw_id"}) is True
        findings = walker.analyze_code(code, language="python", file_path="cast.py")
        # Documents that raw_id is treated as sink at line 4
        sink_vars = [f.sink_node["symbol"] for f in findings]
        assert "raw_id" in sink_vars

    def test_container_blindness_defect_reproduction(self):
        """
        Adversarial Defect Reproduction:
        In dfg.py, _process_expression treats tuple/list nodes as opaque leaf EXPRESSION nodes
        and does not recurse into child elements.
        Therefore, cursor.execute(query, (user_id,)) creates no DFG edge connecting user_id to the sink,
        and walker.analyze_code returns [] instead of reporting a sanitized finding.
        """
        code_qmark = """
import sqlite3
def qmark_safe(request):
    u = request.args.get('u')
    conn = sqlite3.connect("db.sqlite")
    conn.cursor().execute("SELECT * FROM users WHERE name = ?", (u,))
"""
        dfg_b = DFGBuilder()
        dfg = dfg_b.build_for_code(code_qmark, "python", "qmark.py")
        walker = SymbolicTaintWalker()
        srcs = [n for n, d in dfg.nodes(data=True) if walker.is_source_node(d)]
        snks = [n for n, d in dfg.nodes(data=True) if walker.is_sink_node(d)]

        # Prove empirically that no edge connects source to sink due to tuple container opacity
        for s in srcs:
            for k in snks:
                assert not nx.has_path(dfg, s, k), "DFG fails to connect source to sink across tuple container"

        findings = walker.analyze_code(code_qmark, language="python", file_path="qmark.py")
        assert len(findings) == 0, "Confirms container blindness bug: findings is empty"


# ============================================================================
# Category 4: Malformed / Syntax-Error Source Files
# ============================================================================

class TestAdversarialSyntaxErrorsAndMalformedFiles:
    """Stress-tests feeding broken syntax, invalid tokens, and truncated files to all builders."""

    @pytest.fixture(autouse=True)
    def setup_managers(self):
        self.cst = CSTParserManager.get_instance()
        self.cfg_builder = CFGBuilder()
        self.dfg_builder = DFGBuilder()
        self.engine = MaintainabilityEngine()
        self.walker = SymbolicTaintWalker()

    def test_truncated_python_syntax_error(self):
        """Unclosed function header and missing body."""
        code = "def broken_fn(x, y:\n"
        tree = self.cst.parse(code, language="python")
        assert self.cst.has_syntax_errors(tree) is True

        cg = CallGraphBuilder()
        cg.add_file("trunc.py", code=code, language="python")
        cg.build()

        self.cfg_builder.build_for_code(code, language="python", file_path="trunc.py")
        self.dfg_builder.build_for_code(code, language="python", file_path="trunc.py")
        metrics = self.engine.analyze_code(code, language="python", file_path="trunc.py")
        assert metrics.file_sloc >= 1
        findings = self.walker.analyze_code(code, language="python", file_path="trunc.py")
        assert isinstance(findings, list)

    def test_truncated_javascript_unclosed_block(self):
        """Unclosed curly braces and unfinished expression statement."""
        code = "function broken(a, b) { if (a > 0) { const x = "
        tree = self.cst.parse(code, language="javascript")
        assert self.cst.has_syntax_errors(tree) is True

        cg = CallGraphBuilder()
        cg.add_file("trunc.js", code=code, language="javascript")
        cg.build()

        self.cfg_builder.build_for_code(code, language="javascript", file_path="trunc.js")
        self.dfg_builder.build_for_code(code, language="javascript", file_path="trunc.js")
        metrics = self.engine.analyze_code(code, language="javascript", file_path="trunc.js")
        assert metrics.file_sloc >= 1
        findings = self.walker.analyze_code(code, language="javascript", file_path="trunc.js")
        assert isinstance(findings, list)

    def test_random_token_soup_garbage(self):
        """Pure symbol soup with no valid programming constructs."""
        code = "@#$%^&*()_+=-[]{};':\",.<>/?\n!~`|||&&&^^^%%$$#"
        tree = self.cst.parse(code, language="python")
        assert self.cst.has_syntax_errors(tree) is True

        cg = CallGraphBuilder()
        cg.add_file("garbage.py", code=code, language="python")
        cg.build()

        self.cfg_builder.build_for_code(code, language="python", file_path="garbage.py")
        self.dfg_builder.build_for_code(code, language="python", file_path="garbage.py")
        metrics = self.engine.analyze_code(code, language="python", file_path="garbage.py")
        assert metrics.cyclomatic_complexity >= 1
        findings = self.walker.analyze_code(code, language="python", file_path="garbage.py")
        assert isinstance(findings, list)

    def test_empty_and_whitespace_sources(self):
        """Empty string and whitespace-only files."""
        for empty_code in ["", "    \n\t  \n  "]:
            tree = self.cst.parse(empty_code, language="python")
            assert tree.root_node is not None

            cg = CallGraphBuilder()
            cg.add_file("empty.py", code=empty_code, language="python")
            cg.build()

            self.cfg_builder.build_for_code(empty_code, language="python", file_path="empty.py")
            self.dfg_builder.build_for_code(empty_code, language="python", file_path="empty.py")
            metrics = self.engine.analyze_code(empty_code, language="python", file_path="empty.py")
            assert metrics.file_sloc == 1
            findings = self.walker.analyze_code(empty_code, language="python", file_path="empty.py")
            assert findings == []

    def test_embedded_null_bytes(self):
        """Source strings containing embedded null bytes \\x00."""
        code = "def null_fn():\x00\x00\n    return 'safe'\x00\n"
        tree = self.cst.parse(code, language="python")
        assert tree.root_node is not None

        cg = CallGraphBuilder()
        cg.add_file("null.py", code=code, language="python")
        cg.build()

        self.cfg_builder.build_for_code(code, language="python", file_path="null.py")
        self.dfg_builder.build_for_code(code, language="python", file_path="null.py")
        metrics = self.engine.analyze_code(code, language="python", file_path="null.py")
        assert metrics.file_sloc >= 1

    def test_deeply_nested_parentheses_cst(self):
        """200 levels of nested parentheses: (((...1...)))."""
        code = "x = " + "(" * 200 + "1" + ")" * 200
        tree = self.cst.parse(code, language="python")
        assert tree.root_node is not None

        self.dfg_builder.build_for_code(code, language="python", file_path="parens.py")
        metrics = self.engine.analyze_code(code, language="python", file_path="parens.py")
        assert metrics.file_sloc >= 1

    def test_maintainability_metrics_schema_invariants_on_malformed_input(self):
        """Even on heavily malformed input, exactly the 8 ISO/IEC 25010 metrics are produced."""
        code = "class { def : [ ; function }}}"
        metrics = self.engine.analyze_code(code, language="python", file_path="malformed.py")
        metric_dict = metrics.model_dump()

        required_keys = {
            "cyclomatic_complexity",
            "cognitive_complexity",
            "parameter_count",
            "function_sloc",
            "file_sloc",
            "module_coupling_ce",
            "module_coupling_ca",
            "duplicated_blocks",
            "comment_density",
        }
        for k in required_keys:
            assert k in metric_dict
            assert metric_dict[k] is not None
            assert metric_dict[k] >= 0

        forbidden_keys = {"sqale_rating", "lcom4", "dit", "nom", "raw_loc", "nesting_depth"}
        for f_k in forbidden_keys:
            assert f_k not in metric_dict
