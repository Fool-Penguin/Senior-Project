"""
test_adversarial_dfg_taint.py
Empirical Adversarial Stress Testing Suite for DFG & Symbolic Taint Walker (Stage 3A).

Authored by: challenger_m2_fix_1
Target Modules:
- codedee/codedee_server/app/graphs/dfg.py
- codedee/codedee_server/app/taint/walker.py

Structure:
- Section 1: Robust Taint Propagation & Control Flow (Confirmed Passing Capabilities)
- Section 2: Negative Controls (Sanitization & Precision Verification)
- Section 3: Empirical Defect Demonstrations (5 Confirmed Evasion Vulnerabilities)
"""

import sys
from pathlib import Path
import pytest

# Ensure codedee_server is importable
SERVER_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "codedee" / "codedee_server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.taint.walker import SymbolicTaintWalker
from app.graphs.dfg import DFGBuilder
from app.models.contracts import SymbolicFinding


@pytest.fixture
def walker():
    return SymbolicTaintWalker()


# ============================================================================
# Section 1: Robust Taint Propagation & Control Flow (Passing Capabilities)
# ============================================================================

def test_ast_nested_tuple_direct_formatting(walker):
    """
    Robustness: Multi-level nested tuple passed directly to % format:
    sql = "... %s ..." % (((username,),),)
    DFG unrolls collections recursively and connects taint into binary op.
    """
    code = """
from flask import request

def handler():
    username = request.args.get("user")
    sql = "SELECT * FROM users WHERE name = '%s'" % (((username,),),)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "nested_tup_direct.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through direct nested tuple formatting"


def test_ast_multi_element_nested_tuple_formatting(walker):
    """
    Robustness: Multi-element nested tuple containing untrusted input alongside constants:
    sql = "... %s ... %s" % (prefix, (user,))
    """
    code = """
from flask import request

def handler():
    prefix = "ACTIVE"
    user = request.args.get("user")
    sql = "SELECT * FROM accounts WHERE status = '%s' AND name = '%s'" % (prefix, (user,))
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "multi_nested_tup.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through multi-element nested tuple"


def test_ast_dictionary_percent_formatting(walker):
    """
    Robustness: Untrusted input inside dictionary used for %(username)s formatting:
    payload = {"username": user, "role": "admin"}
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    payload = {"username": user, "role": "admin"}
    sql = "SELECT * FROM users WHERE name = '%(username)s'" % payload
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "dict_format.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through dictionary % formatting"


def test_ast_set_collection_formatting(walker):
    """
    Robustness: Untrusted input placed inside set collection:
    allowed = {cat}
    """
    code = """
from flask import request

def handler():
    cat = request.args.get("category")
    allowed = {cat}
    sql = "SELECT * FROM products WHERE cat IN %s" % allowed
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "set_collection.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through set collection"


def test_ast_deeply_nested_parenthesized_expression(walker):
    """
    Robustness: Deeply nested redundant grouping parentheses:
    sql = "... " + ((((user))))
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    sql = "SELECT * FROM users WHERE name = '" + ((((user)))) + "'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "nested_parens.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to unwrap deeply nested parenthesized expression"


def test_string_format_positional(walker):
    """
    Robustness: Python str.format() with positional argument:
    sql = "... '{}'".format(user)
    """
    code = """
from flask import request

def handler():
    user = request.args.get("username")
    sql = "SELECT * FROM users WHERE name = '{}'".format(user)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "format_pos.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "str.format() positional argument was not flagged as vulnerable"


def test_augmented_assignment_concat(walker):
    """
    Robustness: String concatenation via augmented assignment (+=):
    sql += " AND category = '" + cat + "'"
    """
    code = """
from flask import request

def handler():
    cat = request.args.get("category")
    sql = "SELECT * FROM products WHERE 1=1"
    sql += " AND category = '" + cat + "'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "aug_assign.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Augmented assignment (+=) taint flow was lost"


def test_javascript_template_literal_in_query_arg(walker):
    """
    Robustness: Inline JavaScript template literal passed directly into db.query argument:
    db.query(`SELECT ... ${req.query.term}`)
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/search', (req, res) => {
    db.query(`SELECT * FROM articles WHERE title LIKE '%${req.query.term}%'`, (err, rows) => {
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "inline_tpl.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Inline JS template literal in query call was not flagged"


def test_typescript_template_literal_with_as_cast(walker):
    """
    Robustness: TypeScript template literal with 'as string' type assertion wrapper:
    `... ${rawUser as string}`
    """
    code = """
import { Request, Response } from 'express';
import { client } from './db';

export async function searchUser(req: Request, res: Response) {
    const rawUser = req.query.user as string;
    const query = `SELECT * FROM members WHERE username = '${rawUser as string}'`;
    const rows = await client.query(query);
    return res.json(rows);
}
"""
    findings = walker.analyze_code(code, "typescript", "ts_cast.ts")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "TypeScript type assertion (as string) broke taint flow"


def test_async_await_parenthesized_javascript(walker):
    """
    Robustness: JavaScript await wrapping a parenthesized query call:
    await (client.query(sql))
    """
    code = """
async function runQuery(req, res) {
    const id = req.params.id;
    const sql = "SELECT * FROM orders WHERE id = " + id;
    const result = await (client.query(sql));
    return result;
}
"""
    findings = walker.analyze_code(code, "javascript", "await_parens.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "JS await (client.query(sql)) parenthesized expression evaded detection"


def test_async_await_typescript_typed_query(walker):
    """
    Robustness: TypeScript typed query expression:
    await (client.query(query) as Promise<any>)
    """
    code = """
export async function getRecord(req: any) {
    const term = req.query.term;
    const query = `SELECT * FROM records WHERE name = '${term}'`;
    const res = await (client.query(query) as Promise<any>);
    return res;
}
"""
    findings = walker.analyze_code(code, "typescript", "ts_typed_await.ts")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "TS typed await expression evaded detection"


def test_multihop_five_hops_assignment_chain(walker):
    """
    Robustness: Tainted value propagated through 5 consecutive variable assignments:
    v1 = req.args -> v2 = v1 -> v3 = v2 -> v4 = v3 -> v5 = v4 -> sql = f"...{v5}"
    """
    code = """
from flask import request

def five_hops():
    v1 = request.args.get("id")
    v2 = v1
    v3 = v2
    v4 = v3
    v5 = v4
    sql = f"SELECT * FROM items WHERE id = {v5}"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "five_hops.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "5-hop Def-Use variable chain was broken"


def test_multihop_branching_reassignment(walker):
    """
    Robustness: Tainted value conditionally assigned inside an if branch:
    if flag: token = request.args.get("token")
    """
    code = """
from flask import request

def branch_logic(flag):
    token = "default"
    if flag:
        token = request.args.get("token")
    sql = "SELECT * FROM sessions WHERE token = '" + token + "'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "branch_logic.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Conditional branching taint assignment was missed"


# ============================================================================
# Section 2: Negative Controls (Sanitization & False Positive Prevention)
# ============================================================================

def test_safe_parameterized_query_tuple(walker):
    """
    Negative Control: Legitimate parameterized query with tuple placeholder:
    cursor.execute(sql, (user, role))
    Must be recognized as sanitized=True.
    """
    code = """
from flask import request

def safe_handler():
    user = request.args.get("user")
    role = request.args.get("role")
    sql = "SELECT * FROM users WHERE name = %s AND role = %s"
    cursor.execute(sql, (user, role))
"""
    findings = walker.analyze_code(code, "python", "safe_tup.py")
    critical_vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(critical_vulns) == 0, f"False positive on legitimate parameterized query: {critical_vulns}"
    assert all(f.sanitized for f in findings), "Parameterized query was not marked sanitized"


def test_safe_parameterized_query_javascript_callback(walker):
    """
    Negative Control: JS parameterized query with callback function:
    db.query("SELECT ... WHERE id = ?", [userId], (err, rows) => ...)
    Must be recognized as sanitized=True.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/user', (req, res) => {
    const userId = req.query.id;
    db.query("SELECT * FROM users WHERE id = ?", [userId], (err, rows) => {
        if (err) return res.status(500).send(err);
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "safe_js.js")
    critical_vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(critical_vulns) == 0, f"False positive on JS parameterized query with callback: {critical_vulns}"


def test_safe_integer_cast_sanitization(walker):
    """
    Negative Control: Python int() type cast sanitizes tainted input:
    clean_id = int(raw_id)
    """
    code = """
from flask import request

def get_by_numeric_id():
    raw_id = request.args.get("id")
    clean_id = int(raw_id)
    sql = f"SELECT * FROM items WHERE id = {clean_id}"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "safe_int.py")
    critical_vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(critical_vulns) == 0, f"False positive on int() cast: {critical_vulns}"
    assert any(f.sanitized for f in findings), "int() cast was not marked sanitized"


def test_safe_constant_fstring_no_user_input(walker):
    """
    Negative Control: Constant-only f-string with no user input:
    f"SELECT ... env = '{env}' LIMIT {limit}"
    Must yield 0 CRITICAL findings.
    """
    code = """
def clean_job():
    env = "PROD"
    limit = 50
    sql = f"SELECT * FROM events WHERE env = '{env}' LIMIT {limit}"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "safe_const.py")
    critical_vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(critical_vulns) == 0, f"False positive on constant f-string: {critical_vulns}"


def test_safe_no_db_call_string_manipulation(walker):
    """
    Negative Control: String operations on untrusted input without SQL sink:
    print(log_line)
    Must yield 0 findings.
    """
    code = """
from flask import request

def logging_handler():
    user = request.args.get("user")
    query_param = request.args.get("q")
    log_line = f"User: {user}, Query: {query_param}"
    print(log_line)
    return log_line
"""
    findings = walker.analyze_code(code, "python", "safe_log.py")
    assert len(findings) == 0, f"False positive on logging/print statements: {findings}"


# ============================================================================
# Section 3: Empirical Defect Demonstrations (5 Confirmed Evasion Vulnerabilities)
# ============================================================================

def test_demonstrate_defect_1_receiver_method_call_drops_taint(walker):
    """
    EMPIRICAL DEFECT PROOF 1 (Receiver Disconnection on Method Invocations):
    In dfg.py:436-467, _process_expression for 'call' nodes processes only argument nodes
    (args_node.children). It completely ignores fn_node!
    When a string manipulation method is called on a tainted variable:
    - fake_clean = raw_user.replace("'", "''")
    - clean = user.strip()
    - clean = raw.trim() (JS/TS)
    The receiver object is omitted from the DFG.
    Blast radius: ANY method call on tainted user input causes 0 findings to be reported!
    """
    code = """
from flask import request

def evasion_method_call():
    raw_user = request.args.get("user")
    fake_clean = raw_user.replace("'", "''")
    sql = f"SELECT * FROM users WHERE name = '{fake_clean}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "defect1_receiver.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    # Verified resolution: Receiver method calls properly propagate taint into DFG
    assert len(vulns) >= 1, (
        "Defect 1 failure: Receiver method calls must propagate taint into DFG!"
    )


def test_demonstrate_defect_2_python_await_syntax_fallthrough(walker):
    """
    EMPIRICAL DEFECT PROOF 2 (Python await AST Node Evasion):
    In dfg.py:534:
    if node_type in ("await_expression", "as_expression", "type_assertion", ...):
    Tree-sitter Python parses 'await cursor.execute(query)' as node type 'await',
    NOT 'await_expression' (which is JS/TS).
    Because 'await' is omitted from the wrapper list, Python await falls through
    to the literal fallback at line 542. cursor.execute is NEVER registered as a CALL_ARG sink!
    Blast radius: 100% of Python asynchronous database queries (await cursor.execute(...)) evade detection!
    """
    code = """
from flask import request

async def async_fetch():
    user = request.args.get("user")
    query = f"SELECT * FROM sessions WHERE user = '{user}'"
    await cursor.execute(query)
"""
    findings = walker.analyze_code(code, "python", "defect2_await.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    # Verified resolution: Python 'await' statements are recognized as syntactic wrappers
    assert len(vulns) >= 1, (
        "Defect 2 failure: Python 'await' statements must be recognized as syntactic wrappers!"
    )


def test_demonstrate_defect_3_keyword_argument_taint_loss(walker):
    """
    EMPIRICAL DEFECT PROOF 3 (Python Keyword Arguments Dropped):
    In dfg.py:456-466, when processing arguments of a call, 'keyword_argument' AST nodes
    (e.g., name=user) have no handler in _process_expression. They fall through to literal fallback,
    dropping the 'value' child ('user').
    Consequently, str.format() with kwargs or any function with kwargs drops taint.
    Blast radius: "...".format(key=user) completely evades detection!
    """
    code = """
from flask import request

def handler():
    user = request.args.get("username")
    sql = "SELECT * FROM users WHERE name = '{name}'".format(name=user)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "defect3_kwargs.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    # Verified resolution: Keyword arguments recursively process value expressions
    assert len(vulns) >= 1, (
        "Defect 3 failure: Keyword arguments must recursively process value expressions!"
    )


def test_demonstrate_defect_4_subscript_indexing_taint_loss(walker):
    """
    EMPIRICAL DEFECT PROOF 4 (Subscript / Indexing Expression Dropped):
    In dfg.py:541-556, AST node type 'subscript' (Python) and 'subscript_expression' (JS/TS)
    are unhandled in _process_expression and fall through to literal fallback.
    Tainted data stored in lists, tuples, or dicts accessed by index (container[0], data['user'])
    loses all connection to the container definition.
    Blast radius: Indexing or subscript access drops taint completely!
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    container = [user]
    sql = "SELECT * FROM items WHERE owner = '%s'" % container[0]
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "defect4_subscript.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    # Verified resolution: Subscript indexing expressions link to container definitions
    assert len(vulns) >= 1, (
        "Defect 4 failure: Subscript indexing expressions must link to container definitions!"
    )


def test_demonstrate_defect_5_dummy_parameter_container_bypass(walker):
    r"""
    EMPIRICAL DEFECT PROOF 5 (Parameterization Bypass via Dummy Containers):
    In walker.py:170 (is_sink_parameterized):
    if re.search(r",\s*(\(|\[|\{)", cleaned): return True
    The walker only inspects the sink call line (cursor.execute(sql, ())).
    If the SQL query was already constructed with an unparameterized f-string on a prior line,
    passing a dummy empty tuple '()' or dict '{}' matches ', (' and tricks the walker into
    marking the finding as sanitized=True with LOW severity!
    Blast radius: Trivial evasion of CWE-89 detection by passing dummy empty parameters!
    """
    code = """
from flask import request

def evasion_empty_tuple():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, ())
"""
    findings = walker.analyze_code(code, "python", "defect5_bypass.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    # Verified resolution: Passing dummy parameters to an interpolated query does NOT sanitize it
    assert len(vulns) >= 1, (
        "Defect 5 failure: cursor.execute(tainted_sql, ()) must be flagged as CRITICAL!"
    )
    assert not any(f.sanitized is True for f in findings), (
        "Defect 5 failure: Empty parameter container was incorrectly marked as sanitized!"
    )
