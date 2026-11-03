"""
test_adversarial_m2_fix.py
Empirical Adversarial Stress-Testing Suite for Milestone 2 Iteration 2 Fixes.

Evaluates:
1. Verification of Defect 1 Fix: Python % tuple formatting evasion.
2. Verification of Defect 2 Fix: False positive rejection on variables named 'raw' or 'query'
   and JS template literal declarations.
3. Precision of JS/TS parameterized query detection with various callback signatures.
4. Correctness of true-positive vs true-negative discrimination on complex patterns.
"""

import sys
from pathlib import Path
import pytest

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.taint.walker import SymbolicTaintWalker
from app.models.contracts import SymbolicFinding


@pytest.fixture
def walker():
    return SymbolicTaintWalker()


# ============================================================================
# 1. Defect 1 Verification: Python % Tuple Formatting Evasion Fix
# ============================================================================

def test_defect1_single_element_tuple_detected(walker):
    """
    Standard Python single-element tuple printf formatting:
    sql = "SELECT * FROM accounts WHERE name = '%s'" % (username,)
    Must connect DFG edge and flag CRITICAL CWE-89 finding.
    """
    code = """
from flask import request

def search_account():
    username = request.args.get("username")
    sql = "SELECT * FROM accounts WHERE name = '%s'" % (username,)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "percent_tuple.py")
    assert len(findings) >= 1, "Failed to detect SQL injection via single-element tuple % formatting!"
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) >= 1, "Single-element tuple formatting must be flagged as CRITICAL unsanitized!"
    
    # Verify taint path traverses through tuple collection
    first = critical[0]
    path_symbols = [step["symbol"] for step in first.taint_path]
    assert any("(username,)" in s or "username" in s for s in path_symbols), (
        f"Taint path does not show variable flow through tuple: {path_symbols}"
    )


def test_defect1_multi_element_tuple_detected(walker):
    """
    Multi-element tuple formatting:
    sql = "SELECT * FROM users WHERE name = '%s' AND role = '%s'" % (user, role)
    Both user and role tainted from request.args.
    """
    code = """
from flask import request

def get_profile():
    user = request.args.get("user")
    role = request.args.get("role")
    sql = "SELECT * FROM users WHERE name = '%s' AND role = '%s'" % (user, role)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "multi_tuple.py")
    assert len(findings) >= 1, "Failed to detect SQL injection via multi-element tuple % formatting!"
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) >= 1, "Multi-element tuple formatting must be flagged as CRITICAL unsanitized!"


def test_defect1_list_formatting_detected(walker):
    """
    List formatting with % operator:
    sql = "SELECT * FROM items WHERE id = '%s'" % [item_id]
    """
    code = """
from flask import request

def get_item():
    item_id = request.args.get("id")
    sql = "SELECT * FROM items WHERE id = '%s'" % [item_id]
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "list_format.py")
    assert len(findings) >= 1, "Failed to detect SQL injection via list % formatting!"
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) >= 1


def test_defect1_nested_parentheses_tuple_detected(walker):
    """
    Nested parenthesized expression in tuple:
    sql = "SELECT * FROM users WHERE name = '%s'" % (((username)),)
    """
    code = """
from flask import request

def search():
    username = request.args.get("q")
    sql = "SELECT * FROM users WHERE name = '%s'" % (((username)),)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "nested_tuple.py")
    assert len(findings) >= 1
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) >= 1, "Nested parentheses in tuple formatting must be unwrapped!"


def test_defect1_dict_formatting_detected(walker):
    """
    Dictionary formatting with % operator:
    sql = "SELECT * FROM users WHERE name = '%(uname)s'" % {"uname": username}
    """
    code = """
from flask import request

def search_dict():
    username = request.args.get("username")
    sql = "SELECT * FROM users WHERE name = '%(uname)s'" % {"uname": username}
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "dict_format.py")
    assert len(findings) >= 1
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) >= 1, "Dictionary formatting with % must be detected!"


def test_defect1_safe_parameterized_query_tuple_is_not_critical(walker):
    """
    Standard DB-API parameterized query passing parameters as a tuple:
    cursor.execute("SELECT * FROM users WHERE name = %s", (username,))
    Must NOT produce any CRITICAL unsanitized findings.
    """
    code = """
from flask import request

def safe_search():
    username = request.args.get("username")
    cursor.execute("SELECT * FROM users WHERE name = %s", (username,))
"""
    findings = walker.analyze_code(code, "python", "safe_tuple.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"Safe parameterized DB-API query falsely flagged as CRITICAL: {critical}"


# ============================================================================
# 2. Defect 2 Verification: False Positive Rejection on Variables 'raw' / 'query'
# ============================================================================

def test_defect2_python_raw_data_and_search_query_variables_zero_findings(walker):
    """
    Python non-SQL function manipulating variables named raw_data, search_query, query_param.
    No database driver methods called. Must return EXACTLY 0 findings.
    """
    code = """
def process_incoming_request(request):
    raw_data = request.args.get('data')
    search_query = request.args.get('q')
    query_param = "filter_active"
    
    transformed = f"{raw_data}:{search_query}:{query_param}"
    return transformed.strip()
"""
    findings = walker.analyze_code(code, "python", "pure_processing.py")
    assert len(findings) == 0, f"False positive findings on safe non-SQL variables: {findings}"


def test_defect2_python_raw_body_json_parsing_zero_findings(walker):
    """
    Python parsing raw JSON payload from request without database calls.
    Must return EXACTLY 0 findings.
    """
    code = """
import json

def parse_user_payload(request):
    raw_body = request.data
    query_payload = json.loads(raw_body)
    return query_payload.get("status")
"""
    findings = walker.analyze_code(code, "python", "json_parser.py")
    assert len(findings) == 0, f"False positive findings on json parsing: {findings}"


def test_defect2_js_raw_and_query_variables_zero_findings(walker):
    """
    JavaScript function manipulating rawInput, searchQuery, queryParams without database calls.
    Must return EXACTLY 0 findings.
    """
    code = """
function handleSearch(req, res) {
    const rawInput = req.query.text;
    const searchQuery = rawInput.trim();
    const queryParams = { q: searchQuery, raw: true };
    res.json(queryParams);
}
"""
    findings = walker.analyze_code(code, "javascript", "search_handler.js")
    assert len(findings) == 0, f"False positive findings on JS search handler: {findings}"


def test_defect2_ts_raw_and_query_variables_zero_findings(walker):
    """
    TypeScript function with typed raw and query variables, no database calls.
    Must return EXACTLY 0 findings.
    """
    code = """
import { Request, Response } from 'express';

export function parseQuery(req: Request, res: Response): void {
    const rawData: string = req.query.data as string;
    const searchFilter: string = rawData ? rawData.toLowerCase() : '';
    const queryResult = { filter: searchFilter, rawCount: 1 };
    res.json(queryResult);
}
"""
    findings = walker.analyze_code(code, "typescript", "ts_handler.ts")
    assert len(findings) == 0, f"False positive findings on TS handler: {findings}"


# ============================================================================
# 3. Stress-Testing JS/TS Template Literals & Declarations
# ============================================================================

def test_js_template_literal_declaration_with_variables_no_db_zero_findings(walker):
    """
    JS template literal assigned to variable `query`, where interpolated variables
    are status and limit, but NO database method execution occurs.
    Must produce EXACTLY 0 findings.
    """
    code = """
function buildQueryString(status, limit) {
    const query = `SELECT * FROM items WHERE status = ${status} LIMIT ${limit}`;
    return query;
}
"""
    findings = walker.analyze_code(code, "javascript", "build_query.js")
    assert len(findings) == 0, f"Template literal declaration falsely flagged as SQL sink: {findings}"


def test_js_template_literal_all_constants_with_db_call_zero_findings(walker):
    """
    JS template literal containing only constant values (status = 'ACTIVE', limit = 20),
    passed to db.query(). No untrusted input is present.
    Must produce EXACTLY 0 findings.
    """
    code = """
function getStaticInventory() {
    const status = "ACTIVE";
    const limit = 20;
    const sql = `SELECT * FROM items WHERE status = '${status}' LIMIT ${limit}`;
    db.query(sql);
}
"""
    findings = walker.analyze_code(code, "javascript", "static_inventory.js")
    assert len(findings) == 0, f"Constant template literal falsely flagged as vulnerability: {findings}"


def test_js_template_literal_integer_boolean_variables_zero_findings(walker):
    """
    Dispatch specified case:
    JS code with `const query = `SELECT * FROM items WHERE status = ${status} LIMIT ${limit}`;`
    where variables are integers / booleans and executed via db.query().
    Must produce ZERO findings.
    """
    code = """
function getApprovedItems() {
    const status = true;
    const limit = 100;
    const query = `SELECT * FROM items WHERE status = ${status} LIMIT ${limit}`;
    db.query(query);
}
"""
    findings = walker.analyze_code(code, "javascript", "int_bool_query.js")
    assert len(findings) == 0, f"Template literal with boolean/integer constants flagged: {findings}"


def test_js_template_literal_html_construction_zero_findings(walker):
    """
    JS template literal constructing HTML markup from untrusted input.
    Must produce EXACTLY 0 findings for CWE-89 (SQL Injection).
    """
    code = """
function renderHtml(req, res) {
    const rawInput = req.query.name;
    const html = `<div class="profile"><h1>Welcome, ${rawInput}</h1></div>`;
    res.send(html);
}
"""
    findings = walker.analyze_code(code, "javascript", "render.js")
    assert len(findings) == 0, f"HTML template literal falsely flagged as SQL injection: {findings}"


# ============================================================================
# 4. Stress-Testing Parameterized Callbacks & Invocation Patterns (JS/TS)
# ============================================================================

def test_js_parameterized_callback_arrow_multi_param(walker):
    """
    JS client.query(sql, [id], (err, rows) => { ... })
    Parameterized query with arrow function callback.
    Must recognize [id] and NOT flag as CRITICAL unsanitized.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/user', (req, res) => {
    const userId = req.query.id;
    const sql = "SELECT * FROM users WHERE id = $1";
    client.query(sql, [userId], (err, rows) => {
        if (err) return res.status(500).send(err);
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "param_arrow.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"Parameterized query with arrow callback falsely flagged as CRITICAL: {critical}"


def test_js_parameterized_callback_function_keyword(walker):
    """
    JS client.query(sql, [id], function(err, rows) { ... })
    Parameterized query with standard function keyword callback.
    Must NOT flag as CRITICAL unsanitized.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/user', (req, res) => {
    const userId = req.query.id;
    const sql = "SELECT * FROM users WHERE id = $1";
    client.query(sql, [userId], function(err, rows) {
        if (err) return res.status(500).send(err);
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "param_func.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"Parameterized query with function callback falsely flagged as CRITICAL: {critical}"


def test_js_parameterized_callback_arrow_single_param(walker):
    """
    JS client.query(sql, [id], err => { ... })
    Parameterized query with single-argument arrow function callback without parens.
    Must NOT flag as CRITICAL unsanitized.
    """
    code = """
const express = require('express');
const router = express.Router();

router.post('/delete', (req, res) => {
    const itemId = req.query.id;
    const sql = "DELETE FROM items WHERE id = $1";
    client.query(sql, [itemId], err => {
        if (err) return res.status(500).send(err);
        res.send("Deleted");
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "param_single_arrow.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"Parameterized query with single-param arrow callback falsely flagged as CRITICAL: {critical}"


def test_js_parameterized_callback_async_arrow(walker):
    """
    JS client.query(sql, [id], async (err, rows) => { ... })
    Parameterized query with async arrow function callback.
    Must NOT flag as CRITICAL unsanitized.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/data', (req, res) => {
    const tag = req.query.tag;
    const sql = "SELECT * FROM posts WHERE tag = $1";
    client.query(sql, [tag], async (err, rows) => {
        await logger.log(rows);
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "param_async.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"Parameterized query with async arrow callback falsely flagged as CRITICAL: {critical}"


def test_js_vulnerable_callback_no_parameter_container_detected(walker):
    """
    Vulnerable contrast:
    client.query(sql, (err, rows) => { ... })
    where sql has template interpolation from req.query.
    No parameter container argument is passed!
    Must be detected as CRITICAL vulnerability.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/user', (req, res) => {
    const name = req.query.name;
    const sql = `SELECT * FROM users WHERE name = '${name}'`;
    client.query(sql, (err, rows) => {
        if (err) return res.status(500).send(err);
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "vuln_callback.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) >= 1, "Vulnerable query with callback but no parameter array failed to be detected!"


def test_js_vulnerable_callback_async_no_parameter_container_detected(walker):
    """
    Vulnerable contrast:
    client.query(sql, async (err, rows) => { ... })
    where sql has template interpolation from req.query.
    Must be detected as CRITICAL vulnerability.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/user', (req, res) => {
    const role = req.query.role;
    const sql = `SELECT * FROM users WHERE role = '${role}'`;
    client.query(sql, async (err, rows) => {
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "vuln_async_callback.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) >= 1, "Vulnerable query with async callback failed to be detected!"


# ============================================================================
# 5. Receiver Whitelist & Non-SQL Method Invocations
# ============================================================================

def test_non_sql_receiver_rejection(walker):
    """
    Calls to methods named query or raw on HTTP receivers or loggers:
    req.query("select * from users"), logger.query("SELECT * FROM debug"), console.raw("dumping raw info")
    Must NOT be classified as SQL execution sinks.
    """
    code = """
def handle_event(req):
    data = req.query("select * from users")
    logger.query("SELECT * FROM debug")
    console.raw("dumping raw info")
    return data
"""
    findings = walker.analyze_code(code, "python", "non_sql_methods.py")
    assert len(findings) == 0, f"Non-SQL receiver calls falsely classified as SQL sinks: {findings}"


def test_type_casting_sanitization_python_and_js(walker):
    """
    Safe integer type casting in Python (int()) and JavaScript (parseInt())
    safely sanitizes numeric tainted inputs.
    Must mark sanitized=True and severity=LOW.
    """
    py_code = """
from flask import request

def get_product():
    raw_id = request.args.get("id")
    safe_id = int(raw_id)
    sql = f"SELECT * FROM products WHERE id = {safe_id}"
    cursor.execute(sql)
"""
    py_findings = walker.analyze_code(py_code, "python", "cast.py")
    assert len(py_findings) >= 1
    assert all(f.sanitized is True for f in py_findings)
    assert all(f.severity == "LOW" for f in py_findings)

    js_code = """
const express = require('express');
const router = express.Router();

router.get('/item', (req, res) => {
    const rawId = req.query.id;
    const safeId = parseInt(rawId, 10);
    const sql = `SELECT * FROM items WHERE id = ${safeId}`;
    db.query(sql);
});
"""
    js_findings = walker.analyze_code(js_code, "javascript", "cast.js")
    assert len(js_findings) >= 1
    assert any(f.sanitized is True and f.severity == "LOW" for f in js_findings)
