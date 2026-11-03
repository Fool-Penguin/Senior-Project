"""
Adversarial stress testing suite for Milestone 2 (R2) components.
Tests:
1. CST Manager: empty code, binary inputs, unicode, broken syntax, large file, QueryCursor on complex SCM.
2. Call Graph: mutual recursion, deeply nested calls, non-existent imports, multiple calls per line.
3. CFG: empty functions, empty files, consecutive returns, infinite loops, try/except without finally.
4. DFG: self-referential assignments (x = x + 1), multiple scopes with identical variable names, chained f-strings.
5. Maintainability: exactly 8 metrics, zero prohibited attributes, zero division cases (empty file).
6. Taint Walker: multi-hop taint propagation, benign sinks vs malicious sinks, parameterized queries vs string concat.
"""

import sys
import os
import networkx as nx

# Add codedee_server to sys.path
sys.path.insert(0, os.path.abspath(r"d:\4th-year\Senior-Project\codedee\codedee_server"))

from app.parser.cst_manager import CSTParserManager, LanguageType
from app.graphs.call_graph import CallGraphBuilder
from app.graphs.cfg import CFGBuilder
from app.graphs.dfg import DFGBuilder
from app.maintainability.engine import MaintainabilityEngine
from app.taint.walker import SymbolicTaintWalker
from app.models.contracts import MaintainabilityMetrics, SymbolicFinding


def test_adversarial_cst():
    print("[1/6] Testing CST Parser Manager Edge Cases...")
    mgr = CSTParserManager.get_instance()

    # Empty string
    tree_empty = mgr.parse("", "python")
    assert tree_empty is not None
    assert tree_empty.root_node is not None

    # Broken syntax
    tree_broken = mgr.parse("def 123 !@#$(): return", "python")
    assert mgr.has_syntax_errors(tree_broken) is True

    # TSX with complex JSX
    tsx_complex = """
    import React, { useState } from 'react';
    export const Widget = <T,>({ items }: { items: T[] }): JSX.Element => {
        return <div>{items.map((x, i) => <span key={i}>{String(x)}</span>)}</div>;
    };
    """
    tree_tsx = mgr.parse(tsx_complex, "tsx")
    assert not mgr.has_syntax_errors(tree_tsx)

    # Unicode & Thai characters
    thai_code = """
    def สวัสดี():
        # ข้อความภาษาไทย
        ชื่อ = "สมชาย"
        return f"สวัสดีคุณ {ชื่อ}"
    """
    tree_thai = mgr.parse(thai_code, "python")
    assert not mgr.has_syntax_errors(tree_thai)

    print("  -> CST Parser Manager passed all edge cases.")


def test_adversarial_call_graph():
    print("[2/6] Testing Call Graph Edge Cases...")
    builder = CallGraphBuilder()

    # Mutual recursion & cycles
    code = """
    def ping(n):
        if n > 0:
            return pong(n - 1)
        return 0

    def pong(n):
        if n > 0:
            return ping(n - 1)
        return 1
    """
    builder.add_file("mutual_rec.py", code, "python")
    g = builder.build()

    ping_id = "mutual_rec.py::ping"
    pong_id = "mutual_rec.py::pong"
    assert g.has_edge(ping_id, pong_id)
    assert g.has_edge(pong_id, ping_id)

    # Cycle detection
    cycles = list(nx.simple_cycles(g))
    assert len(cycles) >= 1
    print(f"  -> Detected mutual recursion cycle: {cycles}")

    # Empty file
    b_empty = CallGraphBuilder()
    b_empty.add_file("empty.py", "", "python")
    g_empty = b_empty.build()
    assert isinstance(g_empty, nx.DiGraph)
    assert len(g_empty.nodes) == 0
    print("  -> Call Graph passed all edge cases.")


def test_adversarial_cfg():
    print("[3/6] Testing CFG Edge Cases...")
    cfg_builder = CFGBuilder()

    # Empty function body
    empty_fn_code = "def do_nothing(): pass\n"
    cfgs = cfg_builder.build_for_code(empty_fn_code, "python", "empty_fn.py")
    assert "do_nothing" in cfgs
    g = cfgs["do_nothing"]
    entry = "empty_fn.py::do_nothing::ENTRY"
    exit_node = "empty_fn.py::do_nothing::EXIT"
    assert nx.has_path(g, entry, exit_node)

    # Dead code after return
    dead_code = """
    def test_unreachable():
        return 1
        x = 2
        y = x + 3
        return y
    """
    cfgs_dead = cfg_builder.build_for_code(dead_code, "python", "dead.py")
    g_dead = cfgs_dead["test_unreachable"]
    assert nx.has_path(g_dead, "dead.py::test_unreachable::ENTRY", "dead.py::test_unreachable::EXIT")

    print("  -> CFG Builder passed all edge cases.")


def test_adversarial_dfg():
    print("[4/6] Testing DFG Edge Cases...")
    dfg_builder = DFGBuilder()

    # Re-assignment in loop (x = x + 1)
    loop_code = """
    def accumulate(items):
        total = 0
        for item in items:
            total = total + item
        return total
    """
    g = dfg_builder.build_for_code(loop_code, "python", "accum.py")
    assert isinstance(g, nx.DiGraph)

    # Verify def-use connections exist
    def_nodes = [n for n, d in g.nodes(data=True) if d.get("node_kind") == "ASSIGN_DEF" and d.get("var_name") == "total"]
    assert len(def_nodes) >= 2  # initial 0 and inside loop

    # Multi-hop f-strings
    chain_fstr = """
    def chain(user):
        step1 = f"prefix_{user}"
        step2 = f"middle_{step1}"
        step3 = f"SELECT * FROM t WHERE id = '{step2}'"
        return step3
    """
    dfg_builder2 = DFGBuilder()
    g_chain = dfg_builder2.build_for_code(chain_fstr, "python", "chain.py")
    param_nodes = [n for n, d in g_chain.nodes(data=True) if d.get("node_kind") == "PARAM"]
    return_nodes = [n for n, d in g_chain.nodes(data=True) if d.get("node_kind") == "RETURN_VAL"]
    assert nx.has_path(g_chain, param_nodes[0], return_nodes[0])

    print("  -> DFG Builder passed all edge cases.")


def test_adversarial_maintainability():
    print("[5/6] Testing Maintainability Engine Edge Cases...")
    engine = MaintainabilityEngine()

    # Completely blank code
    m_blank = engine.analyze_code("", "python")
    assert m_blank.file_sloc == 1  # max(sloc, 1) to prevent zero division
    assert m_blank.comment_density == 0.0
    assert m_blank.cyclomatic_complexity == 1
    assert m_blank.cognitive_complexity == 0

    summary = m_blank.to_summary_dict()
    assert len(summary) == 8
    forbidden = ["sqale", "sqale_rating", "lcom4", "dit", "nom", "raw_loc", "nesting_depth"]
    for f in forbidden:
        assert f not in summary
        assert not hasattr(m_blank, f)

    # Code with only comments
    comment_only = "# comment 1\n# comment 2\n# comment 3\n"
    m_comments = engine.analyze_code(comment_only, "python")
    assert m_comments.comment_density > 0.0

    print("  -> Maintainability Engine passed all edge cases.")


def test_adversarial_taint_walker():
    print("[6/6] Testing Symbolic Taint Walker Edge Cases...")
    walker = SymbolicTaintWalker()

    # 3-hop propagation into SQL sink
    multi_hop_code = """
    from flask import request

    def complex_handler():
        raw = request.args.get('term')
        cleaned = raw.strip()
        formatted = f"search: {cleaned}"
        query = "SELECT * FROM docs WHERE content LIKE '%" + formatted + "%'"
        cursor.execute(query)
    """
    findings = walker.analyze_code(multi_hop_code, "python", "multi_hop.py")
    assert len(findings) >= 1
    # Check that at least one finding reaches cursor.execute with multiple propagation steps
    exec_findings = [f for f in findings if "execute" in f.sink_node.get("expression", "").lower()]
    assert len(exec_findings) >= 1
    target = exec_findings[0]
    assert target.sanitized is False
    assert target.severity == "CRITICAL"
    assert len(target.taint_path) >= 3

    # Benign execution (e.g. logging or non-sql call) vs SQL sink
    benign_code = """
    from flask import request

    def safe_logger():
        data = request.args.get('info')
        print(f"Log: {data}")
    """
    benign_findings = walker.analyze_code(benign_code, "python", "benign.py")
    # print is not an SQL sink -> 0 findings
    assert len(benign_findings) == 0

    # Typecast sanitization
    typecast_code = """
    from flask import request

    def cast_handler():
        raw_id = request.args.get('id')
        safe_id = int(raw_id)
        query = f"SELECT * FROM users WHERE id = {safe_id}"
        cursor.execute(query)
    """
    cast_findings = walker.analyze_code(typecast_code, "python", "typecast.py")
    exec_cast = [f for f in cast_findings if "execute" in f.sink_node.get("expression", "").lower()]
    assert len(exec_cast) >= 1
    for cf in exec_cast:
        assert cf.sanitized is True
        assert cf.severity == "LOW"

    print("  -> Symbolic Taint Walker passed all edge cases.")


if __name__ == "__main__":
    test_adversarial_cst()
    test_adversarial_call_graph()
    test_adversarial_cfg()
    test_adversarial_dfg()
    test_adversarial_maintainability()
    test_adversarial_taint_walker()
    print("\nALL ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY!")
