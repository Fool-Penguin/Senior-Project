"""
test_adversarial_taint_walker.py
Adversarial stress-testing of Symbolic Taint Walker (Stage 3A).

Evaluates:
1. False Positive taint patterns:
   - Template literals and f-strings with numeric/boolean constants (no user input).
   - Variables with 'query' or 'raw' in non-SQL functions.
   - Safe type casting sanitization (int, float, parseInt).
2. False Negative / Sanitization Evasion attempts:
   - Python str.format() invocation with tainted input.
   - Python % tuple formatting evasion.
   - Naive string replacement (replace("'", "''")) vs genuine parameterization.
   - Fake parameter container trick: cursor.execute(tainted_fstring, ()).
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
# 1. False Positive Adversarial Tests
# ============================================================================

def test_fp_constant_numeric_boolean_python_fstring(walker):
    """
    Python f-string containing only constant numbers and booleans must not report
    a CRITICAL SQL injection from untrusted sources.
    """
    code = """
def fetch_system_logs():
    max_records = 100
    is_active = True
    sql = f"SELECT * FROM logs WHERE active = {is_active} LIMIT {max_records}"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "system_logs.py")
    critical_findings = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical_findings) == 0, f"False positive detected: {critical_findings}"


def test_fp_constant_numeric_boolean_javascript_template(walker):
    """
    JS template literal containing only constant numbers and booleans with variable 'sql'
    must not report a CRITICAL SQL injection.
    """
    code = """
function getStaticConfig() {
    const limit = 50;
    const isApproved = true;
    const sql = `SELECT * FROM items WHERE approved = ${isApproved} LIMIT ${limit}`;
    db.query(sql);
}
"""
    findings = walker.analyze_code(code, "javascript", "static_config.js")
    critical_findings = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical_findings) == 0, f"False positive detected: {critical_findings}"


def test_sanitization_type_cast_integer_python(walker):
    """
    Type-casting tainted input to integer via int() safely sanitizes input.
    Walker must mark sanitized=True or severity=LOW.
    """
    code = """
from flask import request

def get_item():
    inp_id = request.args.get("id")
    safe_id = int(inp_id)
    query = f"SELECT * FROM items WHERE id = {safe_id}"
    cursor.execute(query)
"""
    findings = walker.analyze_code(code, "python", "item.py")
    assert len(findings) >= 1
    # All findings must be recognized as sanitized
    for f in findings:
        assert f.sanitized is True
        assert f.severity == "LOW"


def test_sanitization_type_cast_parseint_javascript(walker):
    """
    Type-casting tainted input via parseInt() in JS should be recognized as sanitized.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/items', (req, res) => {
    const inpId = req.query.id;
    const cleanId = parseInt(inpId, 10);
    const sql = `SELECT * FROM items WHERE id = ${cleanId}`;
    db.query(sql);
});
"""
    findings = walker.analyze_code(code, "javascript", "clean_items.js")
    assert len(findings) >= 1
    # Check that the path passing through parseInt is sanitized
    sanitized_findings = [f for f in findings if f.sanitized is True]
    assert len(sanitized_findings) >= 1, "parseInt was not recognized as sanitized!"


# ============================================================================
# 2. False Negative / Evasion Adversarial Tests
# ============================================================================

def test_evasion_str_format_python(walker):
    """
    Tainted input formatted via str.format() into SQL string:
    query = "SELECT * FROM users WHERE username = '{}'".format(username)
    Walker MUST detect this as CWE-89 vulnerability.
    """
    code = """
from flask import request

def find_user():
    username = request.args.get("username")
    query = "SELECT * FROM users WHERE username = '{}'".format(username)
    cursor.execute(query)
"""
    findings = walker.analyze_code(code, "python", "format_attack.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Vulnerability evaded detection via str.format()!"


def test_evasion_naive_string_replace_is_not_sanitized(walker):
    """
    Attempting to sanitize via replace("'", "''") is NOT a safe parameterized query for CWE-89.
    Walker must still flag this as vulnerable (sanitized=False, severity=CRITICAL).
    """
    code = """
from flask import request

def unsafe_replace_handler():
    raw_input = request.args.get("search")
    naive_clean = raw_input.replace("'", "''")
    query = f"SELECT * FROM data WHERE col = '{naive_clean}'"
    cursor.execute(query)
"""
    findings = walker.analyze_code(code, "python", "naive_replace.py")
    assert len(findings) >= 1
    vulns = [f for f in findings if not f.sanitized]
    assert len(vulns) >= 1, "Naive replace() incorrectly treated as parameterized sanitization!"


def test_evasion_fake_empty_tuple_parameter(walker):
    """
    Adversarial test: An attacker or careless developer concatenates user input in f-string,
    but passes an empty tuple () to cursor.execute():
    cursor.execute(query, ())
    Walker should recognize that the query string itself is interpolated/concatenated and flag it.
    """
    code = """
from flask import request

def tricky_fake_param():
    username = request.args.get("username")
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query, ())
"""
    findings = walker.analyze_code(code, "python", "tricky.py")
    assert len(findings) >= 1
    vulns = [f for f in findings if not f.sanitized]
    assert len(vulns) >= 1, "Vulnerability evaded via dummy secondary parameter ()!"


# ============================================================================
# 3. Documented Defect Reproduction Tests (Empirical Findings)
# ============================================================================

def test_reproduce_bug_false_negative_tuple_formatting(walker):
    """
    EMPIRICAL DEFECT PROOF (False Negative):
    In Python, sql = "SELECT * FROM tbl WHERE x = '%s'" % (user_input,) is standard formatting.
    However, DFGBuilder._process_expression drops `tuple` AST nodes without recursing into elements.
    Therefore, the Def-Use edge from user_input into sql is missing, causing 0 findings to be reported!
    """
    code = """
from flask import request

def search_account():
    username = request.args.get("username")
    sql = "SELECT * FROM accounts WHERE name = '%s'" % (username,)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "percent_tuple.py")
    # Document empirical behavior: Currently yields 0 findings (False Negative)
    assert len(findings) == 0, "If this assertion fails, the tuple DFG defect has been fixed!"


def test_reproduce_bug_false_positive_substring_sink_matching(walker):
    """
    EMPIRICAL DEFECT PROOF (False Positive):
    In walker.py, is_sink_node() checks `pattern in var_lower` where SINK_PATTERNS includes 'raw' and 'query'.
    Any variable whose name contains 'raw' (e.g. raw_text) or 'query' (e.g. search_query) is declared
    an SQL EXECUTION SINK, even in code with ZERO database interactions!
    """
    code = """
def parse_raw(request):
    raw_text = request.args.get("text")
    return raw_text.strip()
"""
    findings = walker.analyze_code(code, "python", "pure_text.py")
    # Document empirical behavior: Currently flags 2 critical SQL injections on non-SQL code!
    assert len(findings) >= 1, "Should demonstrate false positive bug"
    assert any(f.sink_node.get("symbol") == "raw_text" for f in findings), (
        "Demonstrated bug: raw_text variable assignment falsely classified as an SQL sink!"
    )


def test_reproduce_bug_false_positive_query_variable_name(walker):
    """
    EMPIRICAL DEFECT PROOF (False Positive):
    In walker.py, _fallback_ast_sink_scan checks `any(p in clean.lower() for p in SINK_PATTERNS)`.
    If a variable is named `query` in a template literal with constant boolean/number:
    const query = `SELECT * FROM tbl WHERE active = ${true}`;
    The line `const query = ...` is treated as an SQL sink, producing a CRITICAL finding.
    """
    code = """
function getStaticConfig() {
    const limit = 50;
    const isApproved = true;
    const query = `SELECT * FROM items WHERE approved = ${isApproved} LIMIT ${limit}`;
    db.query(query);
}
"""
    findings = walker.analyze_code(code, "javascript", "const_query.js")
    # Document empirical behavior: Currently produces a false positive CRITICAL finding
    assert len(findings) >= 1
    assert any(f.severity == "CRITICAL" for f in findings), (
        "Demonstrated bug: const query = template literal with constants falsely flagged as critical vulnerability!"
    )
