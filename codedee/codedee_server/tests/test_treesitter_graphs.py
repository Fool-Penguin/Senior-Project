"""
test_treesitter_graphs.py - Unit tests for Tree-sitter CST parsing and NetworkX graph builders.

Verifies:
1. CST parsing and Tree-sitter 0.26 QueryCursor compatibility for Python, JS, TS, TSX.
2. Call Graph builder (inter-procedural, cross-file imports).
3. Control-Flow Graph (CFG) builder (if/else, loops, try/catch/finally).
4. Data-Flow Graph (DFG) builder (Def-Use chains, string concat, template literals, parameter bindings).
"""

import os
import networkx as nx
import pytest

from app.parser.cst_manager import CSTParserManager, LanguageType
from app.graphs.call_graph import CallGraphBuilder
from app.graphs.cfg import CFGBuilder
from app.graphs.dfg import DFGBuilder


# ============================================================================
# 1. Tree-sitter CST Parsing Tests
# ============================================================================

def test_cst_manager_singleton():
    mgr1 = CSTParserManager.get_instance()
    mgr2 = CSTParserManager.get_instance()
    assert mgr1 is mgr2


def test_cst_language_detection():
    mgr = CSTParserManager.get_instance()
    assert mgr.detect_language("app/controller.py") == LanguageType.PYTHON.value
    assert mgr.detect_language("src/index.js") == LanguageType.JAVASCRIPT.value
    assert mgr.detect_language("src/index.mjs") == LanguageType.JAVASCRIPT.value
    assert mgr.detect_language("src/service.ts") == LanguageType.TYPESCRIPT.value
    assert mgr.detect_language("src/Component.tsx") == LanguageType.TSX.value


def test_cst_content_sniffing():
    mgr = CSTParserManager.get_instance()
    py_code = "def calculate(x):\n    return x * 2\n"
    js_code = "function calculate(x) {\n    return x * 2;\n}\n"
    ts_code = "function calculate(x: number): number {\n    return x * 2;\n}\n"
    tsx_code = "const App = () => { return <div className='main'>Hello</div>; };"

    assert mgr.detect_language("unknown", py_code) == LanguageType.PYTHON.value
    assert mgr.detect_language("unknown", js_code) == LanguageType.JAVASCRIPT.value
    assert mgr.detect_language("unknown", ts_code) == LanguageType.TYPESCRIPT.value
    assert mgr.detect_language("unknown", tsx_code) == LanguageType.TSX.value


def test_cst_parse_python():
    mgr = CSTParserManager.get_instance()
    code = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
    tree = mgr.parse(code, LanguageType.PYTHON)
    assert tree is not None
    assert tree.root_node.type == "module"
    assert not mgr.has_syntax_errors(tree)


def test_cst_parse_javascript():
    mgr = CSTParserManager.get_instance()
    code = "const add = (a, b) => a + b;\nconsole.log(add(1, 2));\n"
    tree = mgr.parse(code, LanguageType.JAVASCRIPT)
    assert tree is not None
    assert tree.root_node.type == "program"
    assert not mgr.has_syntax_errors(tree)


def test_cst_parse_typescript_and_tsx():
    mgr = CSTParserManager.get_instance()
    ts_code = "interface User { id: number; name: string; }\nconst u: User = { id: 1, name: 'Alice' };"
    tree_ts = mgr.parse(ts_code, LanguageType.TYPESCRIPT)
    assert tree_ts.root_node.type == "program"
    assert not mgr.has_syntax_errors(tree_ts)

    tsx_code = "import React from 'react';\nexport const Banner = () => <h1>Welcome</h1>;"
    tree_tsx = mgr.parse(tsx_code, LanguageType.TSX)
    assert tree_tsx.root_node.type == "program"
    assert not mgr.has_syntax_errors(tree_tsx)


def test_cst_query_cursor_compatibility_v026():
    """Verify that QueryCursor handles queries on 0.26 without AttributeError."""
    mgr = CSTParserManager.get_instance()
    code = "def find_user(user_id):\n    return user_id\n"
    tree = mgr.parse(code, "python")

    query_str = "(function_definition name: (identifier) @fn.name) @fn.def"
    captures = mgr.query_captures(query_str, tree.root_node, "python")
    assert "fn.name" in captures
    assert len(captures["fn.name"]) == 1
    fn_name = mgr.get_node_text(captures["fn.name"][0])
    assert fn_name == "find_user"

    matches = mgr.query_matches(query_str, tree.root_node, "python")
    assert len(matches) == 1
    pattern_idx, match_caps = matches[0]
    assert pattern_idx == 0
    assert "fn.name" in match_caps


def test_cst_syntax_error_detection():
    mgr = CSTParserManager.get_instance()
    broken_code = "def broken_func(:\n    pass\n"
    tree = mgr.parse(broken_code, "python")
    assert mgr.has_syntax_errors(tree) is True


# ============================================================================
# 2. NetworkX Call Graph Tests
# ============================================================================

def test_call_graph_intra_procedural():
    builder = CallGraphBuilder()
    code = """
def helper(x):
    return x * 2

def main():
    val = helper(10)
    return val
"""
    builder.add_file("app/main.py", code, "python")
    graph = builder.build()

    assert isinstance(graph, nx.DiGraph)
    caller_id = "app/main.py::main"
    callee_id = "app/main.py::helper"

    assert caller_id in graph.nodes
    assert callee_id in graph.nodes
    assert graph.has_edge(caller_id, callee_id)

    edge_data = graph[caller_id][callee_id]
    assert edge_data["call_line"] == 6
    assert "10" in edge_data["arguments"]


def test_call_graph_cross_file_imports(tmp_path):
    builder = CallGraphBuilder()
    mod_a = tmp_path / "service.py"
    mod_b = tmp_path / "controller.py"

    mod_a.write_text("""
def query_db(table, filter_exp):
    return f"SELECT * FROM {table} WHERE {filter_exp}"
""", encoding="utf-8")

    mod_b.write_text(f"""
from service import query_db

def handle_request(req):
    return query_db("users", "id = 1")
""", encoding="utf-8")

    builder.add_file(str(mod_a), language="python")
    builder.add_file(str(mod_b), language="python")
    graph = builder.build()

    controller_id = f"{os.path.normpath(str(mod_b)).replace('\\', '/')}::handle_request"
    service_id = f"{os.path.normpath(str(mod_a)).replace('\\', '/')}::query_db"

    assert controller_id in graph.nodes
    assert service_id in graph.nodes
    assert graph.has_edge(controller_id, service_id)


def test_call_graph_javascript_imports(tmp_path):
    builder = CallGraphBuilder()
    mod_a = tmp_path / "db.js"
    mod_b = tmp_path / "routes.js"

    mod_a.write_text("""
export function executeRaw(sql) {
    return sql;
}
""", encoding="utf-8")

    mod_b.write_text("""
import { executeRaw } from './db';

function getItems() {
    return executeRaw("SELECT * FROM items");
}
""", encoding="utf-8")

    builder.add_file(str(mod_a), language="javascript")
    builder.add_file(str(mod_b), language="javascript")
    graph = builder.build()

    route_id = f"{os.path.normpath(str(mod_b)).replace('\\', '/')}::getItems"
    db_id = f"{os.path.normpath(str(mod_a)).replace('\\', '/')}::executeRaw"

    assert route_id in graph.nodes
    assert db_id in graph.nodes
    assert graph.has_edge(route_id, db_id)


def test_call_graph_external_calls():
    builder = CallGraphBuilder()
    code = """
def fetch_data(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
"""
    builder.add_file("fetch.py", code, "python")
    graph = builder.build()

    caller_id = "fetch.py::fetch_data"
    assert caller_id in graph.nodes
    callees = list(graph.successors(caller_id))
    assert any("execute" in c for c in callees)


# ============================================================================
# 3. NetworkX Control-Flow Graph (CFG) Tests
# ============================================================================

def test_cfg_python_branching():
    cfg_builder = CFGBuilder()
    code = """
def process_score(score):
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    else:
        grade = "C"
    return grade
"""
    cfgs = cfg_builder.build_for_code(code, "python", file_path="score.py")
    assert "process_score" in cfgs
    g = cfgs["process_score"]

    assert isinstance(g, nx.DiGraph)
    entry_node = "score.py::process_score::ENTRY"
    exit_node = "score.py::process_score::EXIT"
    assert entry_node in g.nodes
    assert exit_node in g.nodes
    assert nx.has_path(g, entry_node, exit_node)

    edge_types = {d.get("edge_type") for _, _, d in g.edges(data=True)}
    assert "TRUE_BRANCH" in edge_types
    assert "FALSE_BRANCH" in edge_types
    assert "RETURN_EDGE" in edge_types


def test_cfg_loops_and_try_catch():
    cfg_builder = CFGBuilder()
    code = """
def run_worker(items):
    for item in items:
        try:
            val = int(item)
        except ValueError:
            val = 0
    return val
"""
    cfgs = cfg_builder.build_for_code(code, "python", file_path="worker.py")
    g = cfgs["run_worker"]

    block_types = {d.get("block_type") for _, d in g.nodes(data=True)}
    assert "LOOP_HEADER" in block_types
    assert "TRY_HEADER" in block_types
    assert "CATCH_BLOCK" in block_types

    edge_types = {d.get("edge_type") for _, _, d in g.edges(data=True)}
    assert "LOOP_BODY" in edge_types
    assert "EXCEPTION_EDGE" in edge_types


def test_cfg_javascript_branching():
    cfg_builder = CFGBuilder()
    code = """
function checkStatus(status) {
    if (status === 'active') {
        return true;
    } else {
        return false;
    }
}
"""
    cfgs = cfg_builder.build_for_code(code, "javascript", file_path="status.js")
    assert "checkStatus" in cfgs
    g = cfgs["checkStatus"]
    assert nx.has_path(g, "status.js::checkStatus::ENTRY", "status.js::checkStatus::EXIT")


# ============================================================================
# 4. NetworkX Data-Flow Graph (DFG) Tests
# ============================================================================

def test_dfg_def_use_chain():
    dfg_builder = DFGBuilder()
    code = """
def compute(x):
    y = x + 10
    z = y * 2
    return z
"""
    graph = dfg_builder.build_for_code(code, "python", file_path="compute.py")
    assert isinstance(graph, nx.DiGraph)

    kinds = {d.get("node_kind") for _, d in graph.nodes(data=True)}
    assert "PARAM" in kinds
    assert "ASSIGN_DEF" in kinds
    assert "VAR_READ" in kinds
    assert "RETURN_VAL" in kinds

    flow_types = {d.get("flow_type") for _, _, d in graph.edges(data=True)}
    assert "DEF_USE" in flow_types
    assert "ASSIGNMENT" in flow_types


def test_dfg_fstring_and_template_literals():
    dfg_builder = DFGBuilder()
    py_code = """
def make_query(user):
    sql = f"SELECT * FROM users WHERE name = {user}"
    return sql
"""
    g_py = dfg_builder.build_for_code(py_code, "python", file_path="query.py")
    kinds_py = {d.get("node_kind") for _, d in g_py.nodes(data=True)}
    assert "INTERPOLATION" in kinds_py
    flows_py = {d.get("flow_type") for _, _, d in g_py.edges(data=True)}
    assert "FORMAT_INTERPOLATION" in flows_py

    dfg_builder_js = DFGBuilder()
    js_code = """
function makeQuery(user) {
    const sql = `SELECT * FROM users WHERE name = ${user}`;
    return sql;
}
"""
    g_js = dfg_builder_js.build_for_code(js_code, "javascript", file_path="query.js")
    kinds_js = {d.get("node_kind") for _, d in g_js.nodes(data=True)}
    assert "INTERPOLATION" in kinds_js
    flows_js = {d.get("flow_type") for _, _, d in g_js.edges(data=True)}
    assert "FORMAT_INTERPOLATION" in flows_js


def test_dfg_string_concatenation():
    dfg_builder = DFGBuilder()
    code = """
def build_statement(table, cond):
    base = "SELECT * FROM " + table
    full = base + " WHERE " + cond
    return full
"""
    graph = dfg_builder.build_for_code(code, "python", file_path="builder.py")
    flows = {d.get("flow_type") for _, _, d in graph.edges(data=True)}
    assert "STRING_CONCAT" in flows


def test_dfg_inter_procedural_argument_binding(tmp_path):
    mod_a = tmp_path / "caller.py"
    mod_b = tmp_path / "callee.py"

    mod_b.write_text("""
def execute_query(conn, raw_sql):
    return raw_sql
""", encoding="utf-8")

    mod_a.write_text("""
from callee import execute_query

def run_flow(user_input):
    q = "SELECT * FROM users WHERE id = " + user_input
    execute_query(None, q)
""", encoding="utf-8")

    cg_b = CallGraphBuilder()
    cg_b.add_file(str(mod_a), language="python")
    cg_b.add_file(str(mod_b), language="python")
    cg = cg_b.build()

    dfg_b = DFGBuilder(call_graph_builder=cg_b)
    dfg_b.build_for_code(mod_a.read_text("utf-8"), "python", str(mod_a))
    dfg_b.build_for_code(mod_b.read_text("utf-8"), "python", str(mod_b))
    dfg_b.link_inter_procedural_calls(cg)

    flows = {d.get("flow_type") for _, _, d in dfg_b.graph.edges(data=True)}
    assert "ARG_TO_PARAM" in flows


def test_dfg_chained_calls_no_node_collision_or_self_loops():
    """Verify chained method calls produce distinct node IDs without self-loops."""
    dfg_builder = DFGBuilder()
    code = """
def run():
    db.get_cursor().execute(query)
"""
    graph = dfg_builder.build_for_code(code, "python", file_path="chain_test.py")
    call_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_kind") == "CALL_ARG"]
    assert len(call_nodes) == 2, f"Expected 2 call nodes (get_cursor and execute), got {len(call_nodes)}"
    # Verify no self-loops exist
    for u, v in graph.edges():
        assert u != v, f"Self-loop detected on node {u}!"


def test_dfg_binary_operations_chained_no_self_loops():
    """Verify chained binary operators produce distinct node IDs without self-loops."""
    dfg_builder = DFGBuilder()
    code = """
def build():
    sql = 'SELECT ' + a + ' FROM ' + b
"""
    graph = dfg_builder.build_for_code(code, "python", file_path="binop_test.py")
    binop_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_kind") == "BINARY_OP"]
    assert len(binop_nodes) >= 3, f"Expected at least 3 binop nodes, got {len(binop_nodes)}"
    for u, v in graph.edges():
        assert u != v, f"Self-loop detected on node {u}!"


def test_dfg_multilevel_subscript_assignment_python():
    """Verify multi-level subscript assignment in Python unwinds to root container identifier."""
    dfg_builder = DFGBuilder()
    code = """
def handler(user):
    data = {"users": [None]}
    data["users"][0] = user
"""
    graph = dfg_builder.build_for_code(code, "python", file_path="sub_test.py")
    # Verify data definition is updated via CONTAINER_MUTATE
    mutate_edges = [(u, v, d) for u, v, d in graph.edges(data=True) if d.get("flow_type") == "CONTAINER_MUTATE"]
    assert len(mutate_edges) >= 1, "Expected CONTAINER_MUTATE edge for nested subscript assignment"
    element_edges = [(u, v, d) for u, v, d in graph.edges(data=True) if d.get("flow_type") == "CONTAINER_ELEMENT"]
    assert len(element_edges) >= 1, "Expected CONTAINER_ELEMENT edge for nested subscript value"


def test_dfg_multilevel_subscript_assignment_javascript():
    """Verify multi-level subscript assignment in JavaScript unwinds to root container identifier."""
    dfg_builder = DFGBuilder()
    code = """
function handler(user) {
    let data = { users: [null] };
    data['users'][0] = user;
}
"""
    graph = dfg_builder.build_for_code(code, "javascript", file_path="sub_test.js")
    mutate_edges = [(u, v, d) for u, v, d in graph.edges(data=True) if d.get("flow_type") == "CONTAINER_MUTATE"]
    assert len(mutate_edges) >= 1, "Expected CONTAINER_MUTATE edge for JS nested subscript assignment"
    element_edges = [(u, v, d) for u, v, d in graph.edges(data=True) if d.get("flow_type") == "CONTAINER_ELEMENT"]
    assert len(element_edges) >= 1, "Expected CONTAINER_ELEMENT edge for JS nested subscript value"


def test_dfg_python_sequence_destructuring():
    """Verify Python tuple/list unpacking creates ASSIGN_DEF nodes for all target variables."""
    dfg_builder = DFGBuilder()
    code = """
def handler(source):
    user, role = source.split(':')
"""
    graph = dfg_builder.build_for_code(code, "python", file_path="unpack_test.py")
    var_names = {d.get("var_name") for _, d in graph.nodes(data=True) if d.get("node_kind") == "ASSIGN_DEF"}
    assert "user" in var_names, "user was not extracted from tuple unpacking"
    assert "role" in var_names, "role was not extracted from tuple unpacking"


def test_dfg_javascript_object_destructuring():
    """Verify JavaScript object destructuring creates ASSIGN_DEF nodes for unpacked properties."""
    dfg_builder = DFGBuilder()
    code = """
function handler(req) {
    const { term } = req.query;
}
"""
    graph = dfg_builder.build_for_code(code, "javascript", file_path="destruct_test.js")
    var_names = {d.get("var_name") for _, d in graph.nodes(data=True) if d.get("node_kind") == "ASSIGN_DEF"}
    assert "term" in var_names, "term was not extracted from object destructuring"


def test_dfg_javascript_array_destructuring():
    """Verify JavaScript array destructuring creates ASSIGN_DEF nodes for array elements."""
    dfg_builder = DFGBuilder()
    code = """
function handler(req) {
    const [first, ...rest] = req.query.items;
}
"""
    graph = dfg_builder.build_for_code(code, "javascript", file_path="arr_destruct_test.js")
    var_names = {d.get("var_name") for _, d in graph.nodes(data=True) if d.get("node_kind") == "ASSIGN_DEF"}
    assert "first" in var_names, "first was not extracted from array destructuring"
    assert "rest" in var_names, "rest was not extracted from array destructuring"


def test_dfg_typescript_aliased_destructuring():
    """Verify TypeScript aliased destructuring extracts the target alias, not the property key."""
    dfg_builder = DFGBuilder()
    code = """
function handler(req: any) {
    const { id: userId } = req.params;
}
"""
    graph = dfg_builder.build_for_code(code, "typescript", file_path="alias_test.ts")
    var_names = {d.get("var_name") for _, d in graph.nodes(data=True) if d.get("node_kind") == "ASSIGN_DEF"}
    assert "userId" in var_names, "userId alias was not extracted from destructuring"
    # id is the key on req.params, NOT the local variable being defined
    assert "id" not in var_names, "key 'id' was incorrectly extracted as local definition"


def test_dfg_javascript_parenthesized_assignment_expression():
    """Verify JS parenthesized assignment expressions unwrapped and processed."""
    dfg_builder = DFGBuilder()
    code = """
function handler(req) {
    let term;
    ({ term } = req.query);
}
"""
    graph = dfg_builder.build_for_code(code, "javascript", file_path="paren_destruct.js")
    def_nodes = [d for _, d in graph.nodes(data=True) if d.get("node_kind") == "ASSIGN_DEF" and d.get("var_name") == "term"]
    assert len(def_nodes) >= 1, "term assignment inside parenthesized expression was not processed"

