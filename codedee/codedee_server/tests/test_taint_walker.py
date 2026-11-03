"""
test_taint_walker.py - Unit tests for Symbolic Taint Walker on CWE-89 SQL Injection.

Verifies:
1. Identifying SQL injection taint paths across Python, JavaScript, and TypeScript.
2. Tracking concatenation (+), % formatting, and interpolations (f-strings, template literals).
3. Parameterized query sanitization detection (?, %s, $1).
4. Cross-file taint path detection using real fixtures from Security_CWE/cross_file_demo/.
5. Strict adherence to SymbolicFinding and TaintPath contracts.
"""

import os
from pathlib import Path
import pytest
from app.taint.walker import SymbolicTaintWalker
from app.models.contracts import SymbolicFinding


@pytest.fixture
def walker():
    return SymbolicTaintWalker()


def test_python_fstring_sql_injection(walker):
    """Verify detection of f-string SQL injection in Python."""
    code = """
from flask import request

def get_profile():
    username = request.args.get("user")
    query = f"SELECT * FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
"""
    findings = walker.analyze_code(code, "python", "profile.py")
    assert len(findings) >= 1

    f = findings[0]
    assert isinstance(f, SymbolicFinding)
    assert f.cwe_id == "CWE-89"
    assert f.sanitized is False
    assert f.severity == "CRITICAL"
    assert "request" in f.source_node.get("symbol", "").lower() or "user" in f.source_node.get("symbol", "").lower()
    assert "user" in f.source_node.get("expression", "").lower()
    assert len(f.taint_path) >= 2


def test_python_concat_sql_injection(walker):
    """Verify detection of string concatenation (+) SQL injection in Python."""
    code = """
def login(request):
    token = request.POST.get("token")
    sql = "SELECT id, role FROM sessions WHERE token = '" + token + "'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "login.py")
    assert len(findings) >= 1
    assert findings[0].sanitized is False


def test_python_percent_format_sql_injection(walker):
    """Verify detection of printf-style % formatting SQL injection in Python."""
    code = """
def search_items(request):
    q = request.args.get("q")
    sql = "SELECT * FROM items WHERE name LIKE '%%%s%%'" % q
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "search.py")
    assert len(findings) >= 1
    assert findings[0].sanitized is False


def test_python_parameterized_query_sanitized(walker):
    """Verify that parameterized queries are recognized as sanitized (SAFE)."""
    code = """
from flask import request

def safe_lookup():
    user_id = request.args.get("id")
    query = "SELECT * FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))
"""
    findings = walker.analyze_code(code, "python", "safe_lookup.py")
    for f in findings:
        assert f.sanitized is True
        assert f.severity == "LOW"


def test_javascript_template_literal_sql_injection(walker):
    """Verify detection of template literal interpolation in JavaScript."""
    js_code = """
const express = require('express');
const router = express.Router();

router.get('/products', (req, res) => {
    const category = req.query.category;
    const sql = `SELECT * FROM products WHERE category = '${category}'`;
    db.query(sql, (err, rows) => {
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(js_code, "javascript", "products.js")
    assert len(findings) >= 1
    f = findings[0]
    assert f.cwe_id == "CWE-89"
    assert f.sanitized is False
    assert f.severity == "CRITICAL"


def test_typescript_concat_sql_injection(walker):
    """Verify detection of concatenation SQL injection in TypeScript."""
    ts_code = """
import { Request, Response } from 'express';
import { client } from './database';

export async function getUser(req: Request, res: Response) {
    const userId = req.params.id;
    const query = "SELECT * FROM users WHERE id = " + userId;
    const result = await client.query(query);
    return res.json(result);
}
"""
    findings = walker.analyze_code(ts_code, "typescript", "users.ts")
    assert len(findings) >= 1
    assert findings[0].sanitized is False


def test_cross_file_taint_path(walker):
    """
    Verify inter-procedural taint propagation across files using the demo in Security_CWE/cross_file_demo/.
    api_controller.py (source) -> storage_service.py (sink).
    """
    controller_path = "Security_CWE/cross_file_demo/api_controller.py"
    storage_path = "Security_CWE/cross_file_demo/storage_service.py"
    if not os.path.exists(controller_path):
        repo_root = Path(__file__).resolve().parents[3]
        controller_path = str(repo_root / "Security_CWE" / "cross_file_demo" / "api_controller.py")
        storage_path = str(repo_root / "Security_CWE" / "cross_file_demo" / "storage_service.py")

    assert os.path.exists(controller_path)
    assert os.path.exists(storage_path)

    findings = walker.analyze_files([controller_path, storage_path])
    assert len(findings) >= 1

    # At least one finding must flag the cross-file SQL injection
    assert any(not f.sanitized for f in findings)
    vulnerable_findings = [f for f in findings if not f.sanitized]
    assert len(vulnerable_findings) > 0

    first_vuln = vulnerable_findings[0]
    assert first_vuln.cwe_id == "CWE-89"
    assert first_vuln.severity == "CRITICAL"
    assert len(first_vuln.taint_path) >= 2


# ============================================================================
# Challenger 2 Defect Remediation Regression Tests (Lock-in Suite)
# ============================================================================

def test_python_percent_format_single_tuple_sql_injection(walker):
    """
    Lock-in Test 1 (Defect 1 Evasion Prevention):
    Single-element tuple formatting: sql = "SELECT * FROM users WHERE name = '%s'" % (user_input,)
    Must be detected as an unparameterized CRITICAL SQL injection (sanitized=False).
    """
    code = """
from flask import request

def get_user_profile():
    username = request.args.get("username")
    sql = "SELECT * FROM users WHERE name = '%s'" % (username,)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "percent_single_tuple.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Vulnerability with % (tuple,) was not detected as CRITICAL!"
    f = vulns[0]
    assert f.cwe_id == "CWE-89"
    assert "username" in f.source_node.get("expression", "") or "request" in f.source_node.get("expression", "")
    assert len(f.taint_path) >= 2


def test_python_percent_format_multi_tuple_sql_injection(walker):
    """
    Lock-in Test 2 (Defect 1 Evasion Prevention):
    Multi-element tuple formatting: sql = "... %s ... %s" % (user_input, role)
    Must be detected as an unparameterized CRITICAL SQL injection.
    """
    code = """
from flask import request

def filter_records():
    user_input = request.args.get("user")
    status = "ACTIVE"
    sql = "SELECT * FROM records WHERE owner = '%s' AND status = '%s'" % (user_input, status)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "percent_multi_tuple.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Multi-element tuple % formatting was not detected as CRITICAL!"
    assert any("user_input" in f.source_node.get("expression", "") for f in vulns)


def test_python_percent_format_list_sql_injection(walker):
    """
    Lock-in Test 3 (Defect 1 Evasion Prevention):
    List collection formatting: sql = "SELECT * FROM items WHERE id = %s" % [item_id]
    Must be detected as an unparameterized CRITICAL SQL injection.
    """
    code = """
from flask import request

def list_lookup():
    item_id = request.args.get("id")
    sql = "SELECT * FROM items WHERE id = %s" % [item_id]
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "percent_list.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "List collection % formatting was not detected as CRITICAL!"


def test_python_non_sql_raw_and_query_variables_not_flagged(walker):
    """
    Lock-in Test 4 (Defect 2 False Positive Prevention):
    Variables containing 'raw' or 'query' (e.g. raw_data, search_query, user_query)
    in code with NO database calls must NOT be flagged as SQL injection sinks.
    """
    code = """
from flask import request

def parse_raw_payload():
    raw_data = request.args.get("data")
    search_query = request.args.get("q")
    raw_text = request.form.get("content")
    user_query = request.values.get("term")
    combined = f"{raw_data} - {search_query} - {raw_text} - {user_query}"
    return combined.strip()
"""
    findings = walker.analyze_code(code, "python", "no_db_raw_vars.py")
    assert len(findings) == 0, f"False positive detected on non-SQL variables: {findings}"


def test_javascript_non_sql_raw_and_query_variables_not_flagged(walker):
    """
    Lock-in Test 5 (Defect 2 False Positive Prevention):
    JavaScript variables named rawData, searchQuery, rawPayload without DB calls
    must NOT be flagged as SQL injection sinks.
    """
    code = """
function processSearchRequest(req, res) {
    const rawData = req.query.data;
    const searchQuery = req.query.q;
    const rawPayload = req.body.payload;
    const queryTerm = req.params.term;
    const summary = `Query: ${searchQuery}, Raw: ${rawData}, Term: ${queryTerm}`;
    return res.json({ summary: summary, raw: rawPayload });
}
"""
    findings = walker.analyze_code(code, "javascript", "no_db_search_vars.js")
    assert len(findings) == 0, f"False positive detected in JS non-SQL code: {findings}"


def test_javascript_template_literal_non_sql_html_not_flagged(walker):
    """
    Lock-in Test 6 (Defect 3 False Positive Prevention):
    Template literal creating HTML/UI without database queries must NOT be flagged.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/render', (req, res) => {
    const rawData = req.query.data;
    const searchQuery = req.query.q;
    const html = `<div class="results"><h3>Search: ${searchQuery}</h3><p>Raw: ${rawData}</p></div>`;
    res.send(html);
});
"""
    findings = walker.analyze_code(code, "javascript", "render_html_template.js")
    assert len(findings) == 0, f"False positive detected on non-SQL template literal: {findings}"


def test_javascript_template_literal_constants_not_flagged(walker):
    """
    Lock-in Test 7 (Defect 3 False Positive Prevention):
    Template literal interpolating only constant numbers/booleans into a variable named 'query'
    with db.query(query) must NOT be flagged as a CRITICAL SQL injection.
    """
    code = """
function getStaticConfig() {
    const limit = 50;
    const isApproved = true;
    const query = `SELECT * FROM items WHERE approved = ${isApproved} LIMIT ${limit}`;
    db.query(query);
}
"""
    findings = walker.analyze_code(code, "javascript", "const_query_template.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) == 0, f"Template literal with constants falsely flagged as CRITICAL: {vulns}"


def test_raw_variable_with_real_sql_sink_isolates_true_sink(walker):
    """
    Lock-in Test 8 (Isolation & Precision):
    Code containing both a non-SQL variable 'raw_data' and a genuine SQL injection sink
    must flag the genuine sink (cursor.execute) and NOT flag 'raw_data'.
    """
    code = """
from flask import request

def handle_request():
    raw_data = request.args.get("data")
    search_term = request.args.get("term")
    sql = f"SELECT * FROM items WHERE name = '{search_term}'"
    cursor.execute(sql)
    return raw_data
"""
    findings = walker.analyze_code(code, "python", "mixed_sink_precision.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1
    for v in vulns:
        assert v.sink_node.get("symbol") != "raw_data", "raw_data was incorrectly classified as an SQL sink"
        assert "cursor.execute" in v.sink_node.get("expression", "")


# ============================================================================
# Challenger 1 Defect Remediation Regression Lock-in Tests (Defects 1–5)
# ============================================================================

def test_lockin_defect_1_receiver_replace_propagates_taint(walker):
    """
    Lock-in Test (Defect 1 Remediation):
    Receiver method calls like raw_user.replace(...) must propagate taint to
    method return value and flag CRITICAL CWE-89 vulnerability.
    """
    code = """
from flask import request

def evasion_method_call():
    raw_user = request.args.get("user")
    fake_clean = raw_user.replace("'", "''")
    sql = f"SELECT * FROM users WHERE name = '{fake_clean}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect1_replace.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Receiver method invocation (replace) did not propagate taint!"
    assert any("replace" in step.get("symbol", "") or "raw_user" in step.get("symbol", "") for step in vulns[0].taint_path)
    assert len(vulns[0].taint_path) >= 4


def test_lockin_defect_1_receiver_strip_propagates_taint(walker):
    """
    Lock-in Test (Defect 1 Remediation):
    Receiver method calls like user.strip() must propagate taint to method return value.
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    clean = user.strip()
    sql = f"SELECT * FROM users WHERE name = '{clean}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect1_strip.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Receiver method invocation (strip) did not propagate taint!"
    assert len(vulns[0].taint_path) >= 4


def test_lockin_defect_1_receiver_chained_js_propagates_taint(walker):
    """
    Lock-in Test (Defect 1 Remediation):
    Chained JavaScript receiver method invocations raw.trim().toLowerCase()
    must propagate taint to sink and flag CRITICAL CWE-89.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/user', (req, res) => {
    const raw = req.query.user;
    const clean = raw.trim().toLowerCase();
    const sql = `SELECT * FROM users WHERE name = '${clean}'`;
    db.query(sql);
});
"""
    findings = walker.analyze_code(code, "javascript", "lockin_defect1_chained.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Chained JS receiver methods did not propagate taint!"
    assert len(vulns[0].taint_path) >= 4


def test_lockin_defect_2_python_await_sink_detected(walker):
    """
    Lock-in Test (Defect 2 Remediation):
    Python async database calls with 'await cursor.execute(...)' must be recognized
    as SQL sinks and flagged as CRITICAL SQL injection.
    """
    code = """
from flask import request

async def async_fetch():
    user = request.args.get("user")
    query = f"SELECT * FROM sessions WHERE user = '{user}'"
    await cursor.execute(query)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect2_await.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Python 'await cursor.execute(...)' sink was not detected!"
    assert any("cursor.execute" in v.sink_node.get("expression", "") for v in vulns)
    assert len(vulns[0].taint_path) >= 3


def test_lockin_defect_3_keyword_argument_taint_propagates(walker):
    """
    Lock-in Test (Defect 3 Remediation):
    Python keyword arguments (e.g. str.format(name=user)) must propagate taint
    and flag CRITICAL SQL injection.
    """
    code = """
from flask import request

def handler():
    user = request.args.get("username")
    sql = "SELECT * FROM users WHERE name = '{name}'".format(name=user)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect3_kwargs.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Python keyword argument (name=user) taint was dropped!"
    assert len(vulns[0].taint_path) >= 3


def test_lockin_defect_4_subscript_indexing_list_propagates(walker):
    """
    Lock-in Test (Defect 4 Remediation):
    Subscript access container[0] must propagate taint from collection definition
    to use site and flag CRITICAL SQL injection.
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    container = [user]
    sql = "SELECT * FROM items WHERE owner = '%s'" % container[0]
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect4_subscript.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Subscript indexing (container[0]) dropped taint!"
    assert len(vulns[0].taint_path) >= 4


def test_lockin_defect_4_subscript_indexing_dict_propagates(walker):
    """
    Lock-in Test (Defect 4 Remediation):
    Dictionary subscript access data['user'] must propagate taint to SQL sink.
    """
    code = """
from flask import request

def handler():
    raw_user = request.args.get("user")
    data = {"user": raw_user}
    sql = f"SELECT * FROM items WHERE owner = '{data['user']}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect4_dict.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Dict subscript indexing (data['user']) dropped taint!"
    assert len(vulns[0].taint_path) >= 4


def test_lockin_defect_4_subscript_assignment_mutation_propagates(walker):
    """
    Lock-in Test (Defect 4 Remediation):
    LHS subscript assignment container[0] = user must update definition and propagate taint.
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    container = ["initial"]
    container[0] = user
    sql = "SELECT * FROM items WHERE owner = '%s'" % container[0]
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect4_assign.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Subscript assignment mutation (container[0] = user) dropped taint!"
    assert len(vulns[0].taint_path) >= 4


def test_lockin_defect_5_empty_tuple_bypass_rejected(walker):
    """
    Lock-in Test (Defect 5 Remediation):
    Passing an empty tuple () to cursor.execute(sql, ()) when sql was constructed via f-string
    must NOT be marked sanitized and MUST be flagged as CRITICAL SQL injection.
    """
    code = """
from flask import request

def evasion_empty_tuple():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, ())
"""
    findings = walker.analyze_code(code, "python", "lockin_defect5_tuple.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Empty tuple container bypass was not flagged as CRITICAL!"
    assert not any(f.sanitized is True for f in findings), "Empty tuple container was marked sanitized!"


def test_lockin_defect_5_empty_list_and_dict_bypass_rejected(walker):
    """
    Lock-in Test (Defect 5 Boundary Remediation):
    Passing empty list [] or empty dict {} to cursor.execute when sql was constructed
    via f-string must be rejected and flagged as CRITICAL.
    """
    code_list = """
from flask import request

def evasion_empty_list():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, [])
"""
    findings_list = walker.analyze_code(code_list, "python", "lockin_defect5_list.py")
    vulns_list = [f for f in findings_list if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns_list) >= 1, "Empty list container bypass was not flagged as CRITICAL!"

    code_dict = """
from flask import request

def evasion_empty_dict():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, {})
"""
    findings_dict = walker.analyze_code(code_dict, "python", "lockin_defect5_dict.py")
    vulns_dict = [f for f in findings_dict if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns_dict) >= 1, "Empty dict container bypass was not flagged as CRITICAL!"


def test_lockin_defect_5_dummy_parameter_with_interpolated_query_rejected(walker):
    """
    Lock-in Test (Defect 5 Non-Empty Dummy Container Remediation):
    Passing non-empty dummy parameters ("dummy",) to cursor.execute(sql, ("dummy",))
    where sql was constructed with an unparameterized f-string must NOT sanitize the flaw!
    """
    code = """
from flask import request

def evasion_dummy_param():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, ("dummy",))
"""
    findings = walker.analyze_code(code, "python", "lockin_defect5_dummy.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Dummy parameters bypassed interpolated query detection!"
    assert not any(f.sanitized is True for f in findings)


def test_lockin_defect_5_javascript_empty_array_bypass_rejected(walker):
    """
    Lock-in Test (Defect 5 JS Remediation):
    Passing empty array [] to db.query(sql, []) when sql was formed via template literal
    must be flagged as CRITICAL.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/user', (req, res) => {
    const userId = req.query.id;
    const sql = `SELECT * FROM users WHERE id = ${userId}`;
    db.query(sql, []);
});
"""
    findings = walker.analyze_code(code, "javascript", "lockin_defect5_js.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "JS empty array bypass was not flagged as CRITICAL!"


def test_lockin_defect_5_typescript_empty_array_bypass_rejected(walker):
    """
    Lock-in Test (Defect 5 TS Remediation):
    Passing empty array [] to client.query(query, []) when query was formed via template literal
    must be flagged as CRITICAL.
    """
    code = """
import { Request, Response } from 'express';
import { client } from './db';

export async function getUser(req: Request, res: Response) {
    const userId = req.query.id;
    const query = `SELECT * FROM users WHERE id = ${userId}`;
    await client.query(query, []);
}
"""
    findings = walker.analyze_code(code, "typescript", "lockin_defect5_ts.ts")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "TS empty array bypass was not flagged as CRITICAL!"


def test_lockin_defect_5_legitimate_parameterized_queries_remain_sanitized(walker):
    """
    Lock-in Test (Defect 5 Non-Regression Positive Control):
    Legitimate parameterized queries with non-empty containers must remain marked sanitized=True.
    """
    py_code = """
from flask import request

def safe_handler():
    user = request.args.get("user")
    cursor.execute("SELECT * FROM users WHERE name = %s", (user,))
"""
    py_findings = walker.analyze_code(py_code, "python", "lockin_safe_py.py")
    assert all(f.sanitized is True and f.severity == "LOW" for f in py_findings)
    assert not any(not f.sanitized for f in py_findings)

    js_code = """
router.get('/user', (req, res) => {
    const userId = req.query.id;
    db.query("SELECT * FROM users WHERE id = ?", [userId], (err, rows) => {});
});
"""
    js_findings = walker.analyze_code(js_code, "javascript", "lockin_safe_js.js")
    assert all(f.sanitized is True and f.severity == "LOW" for f in js_findings)


def test_defect_1_shortest_path_parameter_bypass_python_concat(walker):
    """Verify that unparameterized string concatenation with secondary parameter container is flagged CRITICAL."""
    code = """
from flask import request

def search():
    user = request.args.get('user')
    sql = "SELECT * FROM users WHERE name = '" + user + "'"
    cursor.execute(sql, (user,))
"""
    findings = walker.analyze_code(code, "python", "bypass_concat.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Shortest-path parameter bypass was not flagged as CRITICAL!"


def test_defect_1_shortest_path_parameter_bypass_python_fstring(walker):
    """Verify that unparameterized f-string query with secondary parameter container is flagged CRITICAL."""
    code = """
from flask import request

def search():
    user = request.args.get('user')
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, (user,))
"""
    findings = walker.analyze_code(code, "python", "bypass_fstring.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Shortest-path parameter bypass with f-string was not flagged as CRITICAL!"


def test_defect_1_shortest_path_parameter_bypass_ts_concat(walker):
    """Verify that TypeScript unparameterized concat with secondary parameter container is flagged CRITICAL."""
    code = """
import { Request } from 'express';
export async function filter(req: Request) {
    const id = req.query.id;
    const sql = "SELECT * FROM data WHERE id = " + id;
    await client.query(sql, [id]);
}
"""
    findings = walker.analyze_code(code, "typescript", "bypass_ts.ts")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "TS concat parameter bypass was not flagged as CRITICAL!"


def test_defect_1_shortest_path_parameter_bypass_js_concat(walker):
    """Verify that JavaScript unparameterized concat with secondary parameter container is flagged CRITICAL."""
    code = """
function filter(req) {
    const tag = req.query.tag;
    const sql = "SELECT * FROM items WHERE tag = '" + tag + "'";
    pool.query(sql, [tag]);
}
"""
    findings = walker.analyze_code(code, "javascript", "bypass_js.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "JS concat parameter bypass was not flagged as CRITICAL!"


def test_multiline_sink_call_remains_sanitized(walker):
    """Verify multi-line sink call correctly recognizes parameter container across line breaks."""
    code = """
from flask import request

def safe_handler():
    user = request.args.get("user")
    cursor.execute(
        "SELECT * FROM users WHERE name = %s",
        (user,)
    )
"""
    findings = walker.analyze_code(code, "python", "multiline_safe.py")
    assert all(f.sanitized is True and f.severity == "LOW" for f in findings)
    assert len(findings) >= 1
    # Check that sink_node expression is not truncated to just the first line
    sink_expr = findings[0].sink_node.get("expression", "")
    assert "(user,)" in sink_expr or "%s" in sink_expr


def test_parameter_variable_remains_sanitized(walker):
    """Verify parameter variables passed to sink calls are recognized as parameterized."""
    code = """
from flask import request

def safe_handler():
    user = request.args.get("user")
    params = (user,)
    cursor.execute("SELECT * FROM users WHERE name = %s", params)
"""
    findings = walker.analyze_code(code, "python", "param_var.py")
    assert all(f.sanitized is True and f.severity == "LOW" for f in findings)
    assert len(findings) >= 1


def test_pep249_dictionary_inline_remains_sanitized(walker):
    """Verify PEP 249 dictionary parameter syntax is recognized as sanitized."""
    code = """
from flask import request

def safe_handler():
    user = request.args.get("user")
    cursor.execute("SELECT * FROM users WHERE name = %(name)s", {"name": user})
"""
    findings = walker.analyze_code(code, "python", "pep249_dict.py")
    assert all(f.sanitized is True and f.severity == "LOW" for f in findings)
    assert len(findings) >= 1


def test_pep249_dictionary_variable_remains_sanitized(walker):
    """Verify PEP 249 dictionary parameter variable is recognized as sanitized."""
    code = """
from flask import request

def safe_handler():
    user = request.args.get("user")
    params = {"name": user}
    cursor.execute("SELECT * FROM users WHERE name = %(name)s", params)
"""
    findings = walker.analyze_code(code, "python", "pep249_var.py")
    assert all(f.sanitized is True and f.severity == "LOW" for f in findings)
    assert len(findings) >= 1


def test_chained_sink_call_detection(walker):
    """Verify chained method invocation sinks like db.get_cursor().execute() are detected."""
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    query = f"SELECT * FROM items WHERE owner = '{user}'"
    db.get_cursor().execute(query)
"""
    findings = walker.analyze_code(code, "python", "chained_sink.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Chained sink call was dropped from detection!"


def test_multilevel_subscript_assignment_taint_detection(walker):
    """Verify multi-level subscript assignment mutates container and propagates taint."""
    code = """
from flask import request

def handler():
    data = {"users": [None]}
    user = request.args.get("user")
    data["users"][0] = user
    sql = f"SELECT * FROM users WHERE name = '{data['users'][0]}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "nested_sub.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Nested subscript mutation dropped taint propagation!"


def test_python_destructuring_assignment_taint_detection(walker):
    """Verify Python tuple unpacking propagates taint through destructured variable."""
    code = """
from flask import request

def handler():
    user, role = request.args.get('data').split(':')
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "unpack_taint.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Python unpacking dropped taint propagation!"


def test_js_destructuring_assignment_taint_detection(walker):
    """Verify JavaScript object destructuring propagates taint through destructured variable."""
    code = """
function handler(req) {
    const { term } = req.query;
    const sql = `SELECT * FROM items WHERE title = '${term}'`;
    pool.query(sql);
}
"""
    findings = walker.analyze_code(code, "javascript", "destruct_taint.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "JS destructuring dropped taint propagation!"


