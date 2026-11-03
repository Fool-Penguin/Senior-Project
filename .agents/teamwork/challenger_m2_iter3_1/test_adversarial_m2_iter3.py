"""
test_adversarial_m2_iter3.py
Empirical Adversarial Stress Testing Suite — Milestone 2 Iteration 3
Authored by: challenger_m2_iter3_1

Target Modules:
- codedee/codedee_server/app/graphs/dfg.py
- codedee/codedee_server/app/taint/walker.py

Structure:
- Section 1: Deep Method Chaining (Passing Capabilities: 3-level, 5-level, multi-line, JS, TS)
- Section 2: Python Async Layers & Complex Awaits (Passing Capabilities: double await, kwarg, context)
- Section 3: Nested Subscripting (Passing Capabilities: multi-level reads, 3D matrices, JS object arrays)
- Section 4: Complex Dummy Parameter Container Attacks (Passing Evasion Rejections: ((),), [[],], ({},), etc.)
- Section 5: Negative Controls & Precision Verification (Passing: tuple params, type casts, JS array)
- Section 6: Empirical Defect Demonstrations (3 Confirmed Bugs in M2 Iteration 3)
"""

import sys
from pathlib import Path
import pytest

# Ensure codedee_server is on sys.path
SERVER_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "codedee" / "codedee_server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.taint.walker import SymbolicTaintWalker
from app.graphs.dfg import DFGBuilder


@pytest.fixture
def walker():
    return SymbolicTaintWalker()


# ============================================================================
# Section 1: Deep Method Chaining (Python & JS/TS)
# ============================================================================

def test_python_deep_chaining_three_methods(walker):
    """
    Passing Capability: 3-level chained string method calls:
    raw_user.strip().lower().replace("'", "''")
    """
    code = """
from flask import request

def handler():
    raw_user = request.args.get("user")
    clean = raw_user.strip().lower().replace("'", "''")
    sql = f"SELECT * FROM users WHERE name = '{clean}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "chain3.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through 3 chained method calls"
    assert len(vulns[0].taint_path) >= 3, "Taint path incomplete for 3-level method chaining"


def test_python_deep_chaining_five_methods(walker):
    """
    Passing Capability: 5-level chained method calls with encode/decode:
    raw_user.strip().lower().replace("'", "''").encode('utf-8').decode('utf-8')
    """
    code = """
from flask import request

def handler():
    raw_user = request.args.get("user")
    clean = raw_user.strip().lower().replace("'", "''").encode('utf-8').decode('utf-8')
    sql = f"SELECT * FROM users WHERE name = '{clean}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "chain5.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through 5 chained method calls"


def test_python_multiline_chained_calls(walker):
    """
    Passing Capability: Multi-line fluent method call chaining across parentheses.
    """
    code = """
from flask import request

def handler():
    query_val = (
        request.args.get("user")
        .strip()
        .replace("\\n", "")
        .replace("\\r", "")
        .lower()
    )
    sql = f"SELECT * FROM items WHERE name = '{query_val}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "multiline_chain.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through multi-line method chaining"


def test_javascript_deep_chaining_trim_lower_replace_slice(walker):
    """
    Passing Capability: JavaScript 4-level chained member calls:
    req.query.user.trim().toLowerCase().replace(/'/g, "''").slice(0, 50)
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/profile', (req, res) => {
    const sanitized = req.query.user.trim().toLowerCase().replace(/'/g, "''").slice(0, 50);
    db.query("SELECT * FROM profiles WHERE username = '" + sanitized + "'", (err, rows) => {
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "js_chain.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through JS 4-level method chaining"


def test_typescript_deep_chaining_with_as_type_assertions(walker):
    """
    Passing Capability: TypeScript method chaining on type-asserted receiver:
    (req.query.user as string).trim().toLowerCase().replace(/'/g, "''")
    """
    code = """
import { Request, Response } from 'express';

export function getUser(req: Request, res: Response) {
    const raw = (req.query.user as string).trim().toLowerCase().replace(/'/g, "''");
    const query = `SELECT * FROM users WHERE name = '${raw}'`;
    client.query(query);
}
"""
    findings = walker.analyze_code(code, "typescript", "ts_chain.ts")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through TS type-asserted method chain"


def test_deep_chaining_with_nested_call_arguments(walker):
    """
    Passing Capability: Method chaining where argument itself is a chained method call:
    user.replace(prefix.strip().lower(), "safe")
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    prefix = request.args.get("prefix")
    clean = user.replace(prefix.strip().lower(), "safe")
    sql = f"SELECT * FROM users WHERE name = '{clean}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "nested_arg_chain.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through nested method arguments"


def test_deep_chaining_on_subscript_receiver(walker):
    """
    Passing Capability: Chaining methods directly on subscript access:
    data['user'].strip().lower().replace("'", "''")
    """
    code = """
from flask import request

def handler():
    data = {'user': request.args.get("user")}
    clean = data['user'].strip().lower().replace("'", "''")
    sql = f"SELECT * FROM users WHERE name = '{clean}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "subscript_chain.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through subscript method chain"


# ============================================================================
# Section 2: Python Async Layers & Complex Awaits
# ============================================================================

def test_python_async_double_await_cursor_call(walker):
    """
    Passing Capability: Multiple await levels unwinding:
    await (await get_cursor()).execute(query)
    """
    code = """
from flask import request

async def get_cursor():
    return db.cursor()

async def async_handler():
    user = request.args.get("user")
    query = f"SELECT * FROM sessions WHERE user = '{user}'"
    await (await get_cursor()).execute(query)
"""
    findings = walker.analyze_code(code, "python", "double_await.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through double await cursor execute"


def test_python_async_cursor_execute_with_sql_kwarg(walker):
    """
    Passing Capability: Async cursor execute with named keyword argument:
    await cursor.execute(query=query)
    """
    code = """
from flask import request

async def async_handler():
    user = request.args.get("user")
    query = f"SELECT * FROM sessions WHERE user = '{user}'"
    await cursor.execute(query=query)
"""
    findings = walker.analyze_code(code, "python", "async_kwarg.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through async cursor.execute(query=query)"


def test_python_async_with_async_context_manager_and_await(walker):
    """
    Passing Capability: Async context manager block (async with) containing await cursor.
    """
    code = """
from flask import request

async def async_context_handler():
    user = request.args.get("user")
    query = f"SELECT * FROM accounts WHERE id = '{user}'"
    async with db_pool.acquire() as conn:
        await conn.execute(query)
"""
    findings = walker.analyze_code(code, "python", "async_context.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint inside async with conn.execute block"


# ============================================================================
# Section 3: Nested Dictionary & List Subscripting
# ============================================================================

def test_python_nested_subscript_dict_list_dict(walker):
    """
    Passing Capability: Multi-level nested dictionary and list subscripting reads:
    data['users'][0]['profile']['id']
    """
    code = """
from flask import request

def handler():
    data = {
        'users': [
            {
                'profile': {
                    'id': request.args.get('user')
                }
            }
        ]
    }
    uid = data['users'][0]['profile']['id']
    sql = f"SELECT * FROM profiles WHERE id = '{uid}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "nested_subscript_dict_list.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through nested dict/list subscripts"


def test_python_nested_subscript_three_level_lists(walker):
    """
    Passing Capability: 3-level nested list indexing:
    matrix[0][0][0]
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    matrix = [[[user]]]
    val = matrix[0][0][0]
    sql = f"SELECT * FROM grid WHERE cell = '{val}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "nested_subscript_matrix.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through 3D nested list matrix[0][0][0]"


def test_javascript_nested_subscript_object_array_chain(walker):
    """
    Passing Capability: JavaScript nested object and array subscripting:
    payload.data.items[0]['name']
    """
    code = """
const express = require('express');
const router = express.Router();

router.post('/items', (req, res) => {
    const payload = {
        data: {
            items: [
                { name: req.body.username }
            ]
        }
    };
    const target = payload.data.items[0]['name'];
    db.query("SELECT * FROM items WHERE name = '" + target + "'", (err, rows) => {
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "js_nested_subscript.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through JS nested object/array subscript"


def test_python_subscript_read_with_tainted_index(walker):
    """
    Passing Capability: Subscript read where the index expression itself is tainted.
    """
    code = """
from flask import request

def handler():
    user_idx = request.args.get("col_name")
    cols = {"alpha": "col_a", "beta": "col_b"}
    chosen = cols[user_idx]
    sql = f"SELECT {chosen} FROM data_table"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "tainted_index.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Failed to track taint through dynamic tainted index expression"


# ============================================================================
# Section 4: Complex Dummy Parameter Container Attempts & Evasion Attacks
# ============================================================================

def test_dummy_nested_empty_tuple_with_fstring(walker):
    """
    Passing Evasion Defense: Complex dummy parameter container with nested empty tuple:
    cursor.execute(f"SELECT ...", ((),))
    Flagged as CRITICAL because query was constructed with an f-string.
    """
    code = """
from flask import request

def evasion():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, ((),))
"""
    findings = walker.analyze_code(code, "python", "dummy_nested_tup.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: nested empty tuple ((),) must NOT sanitize f-string query!"
    assert not any(f.sanitized is True for f in findings)


def test_dummy_nested_empty_list_with_fstring(walker):
    """
    Passing Evasion Defense: Complex dummy parameter container with nested empty list:
    cursor.execute(f"SELECT ...", [[],])
    """
    code = """
from flask import request

def evasion():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, [[],])
"""
    findings = walker.analyze_code(code, "python", "dummy_nested_list.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: nested empty list [[],] must NOT sanitize f-string query!"


def test_dummy_nested_empty_dict_with_fstring(walker):
    """
    Passing Evasion Defense: Complex dummy parameter container with nested empty dict:
    cursor.execute(f"SELECT ...", ({},))
    """
    code = """
from flask import request

def evasion():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, ({},))
"""
    findings = walker.analyze_code(code, "python", "dummy_nested_dict.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: nested empty dict ({},) must NOT sanitize f-string query!"


def test_dummy_nonempty_tuple_with_fstring(walker):
    """
    Passing Evasion Defense: Non-empty dummy parameter tuple passed to an already interpolated query:
    cursor.execute(f"SELECT * FROM users WHERE name = '{user}'", ("irrelevant_param",))
    """
    code = """
from flask import request

def evasion():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, ("irrelevant_param",))
"""
    findings = walker.analyze_code(code, "python", "dummy_nonempty_tup.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: non-empty dummy parameter must NOT sanitize f-string query!"
    assert not any(f.sanitized is True for f in findings)


def test_dummy_container_with_concat_query(walker):
    """
    Passing Evasion Defense: Complex dummy parameter container passed to a concatenated query (+):
    cursor.execute("SELECT ... WHERE name = '" + user + "'", ((),))
    """
    code = """
from flask import request

def evasion():
    user = request.args.get("user")
    sql = "SELECT * FROM users WHERE name = '" + user + "'"
    cursor.execute(sql, ((),))
"""
    findings = walker.analyze_code(code, "python", "dummy_concat.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: dummy container must NOT sanitize + concatenated query!"


def test_dummy_container_with_percent_format_query(walker):
    """
    Passing Evasion Defense: Complex dummy parameter container passed to a %-formatted query:
    cursor.execute("SELECT ... WHERE name = '%s'" % user, ((),))
    """
    code = """
from flask import request

def evasion():
    user = request.args.get("user")
    sql = "SELECT * FROM users WHERE name = '%s'" % user
    cursor.execute(sql, ((),))
"""
    findings = walker.analyze_code(code, "python", "dummy_percent.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: dummy container must NOT sanitize % formatted query!"


def test_dummy_container_with_str_format_query(walker):
    """
    Passing Evasion Defense: Complex dummy parameter container passed to a str.format() query:
    cursor.execute("SELECT ... WHERE name = '{}'".format(user), ((),))
    """
    code = """
from flask import request

def evasion():
    user = request.args.get("user")
    sql = "SELECT * FROM users WHERE name = '{}'".format(user)
    cursor.execute(sql, ((),))
"""
    findings = walker.analyze_code(code, "python", "dummy_format.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: dummy container must NOT sanitize str.format query!"


def test_javascript_dummy_nested_array_with_template_literal(walker):
    """
    Passing Evasion Defense: JavaScript nested empty array passed to template literal query:
    db.query(`SELECT ... ${req.query.user}`, [[]]);
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/search', (req, res) => {
    const user = req.query.user;
    const query = `SELECT * FROM users WHERE name = '${user}'`;
    db.query(query, [[]], (err, rows) => {
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "dummy_js_nested_array.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: JS nested empty array [[]] must NOT sanitize template literal!"


def test_javascript_dummy_nonempty_array_with_template_literal(walker):
    """
    Passing Evasion Defense: JavaScript non-empty dummy parameter passed to template literal:
    db.query(`SELECT ... ${req.query.user}`, ["dummy_value"]);
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/search', (req, res) => {
    const user = req.query.user;
    const query = `SELECT * FROM users WHERE name = '${user}'`;
    db.query(query, ["dummy_value"], (err, rows) => {
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "dummy_js_nonempty_array.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Evasion failed: JS dummy parameter must NOT sanitize template literal query!"


# ============================================================================
# Section 5: Negative Controls (Sanitization & Precision Verification)
# ============================================================================

def test_negative_safe_parameterized_with_legitimate_tuple(walker):
    """
    Precision Control: Legitimate parameterized query with tuple parameters:
    cursor.execute("SELECT * FROM users WHERE name = %s", (user,))
    Must be classified as sanitized=True with LOW severity.
    """
    code = """
from flask import request

def safe_handler():
    user = request.args.get("user")
    cursor.execute("SELECT * FROM users WHERE name = %s", (user,))
"""
    findings = walker.analyze_code(code, "python", "safe_param_tuple.py")
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings), "Legitimate parameterized tuple query marked unsanitized!"
    assert all(f.severity == "LOW" for f in findings), "Legitimate parameterized query received high severity!"


def test_negative_safe_parameterized_with_type_cast_int(walker):
    """
    Precision Control: Explicit integer type casting makes f-string interpolation safe:
    user_id = int(request.args.get("id"))
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    """
    code = """
from flask import request

def safe_handler():
    raw_id = request.args.get("id")
    user_id = int(raw_id)
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""
    findings = walker.analyze_code(code, "python", "safe_typecast.py")
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings), "Integer cast sanitized query marked unsanitized!"


def test_negative_safe_parameterized_javascript_array(walker):
    """
    Precision Control: Legitimate parameterized query in JavaScript:
    db.query("SELECT * FROM users WHERE name = $1", [req.query.user])
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/user', (req, res) => {
    db.query("SELECT * FROM users WHERE name = $1", [req.query.user], (err, rows) => {
        res.json(rows);
    });
});
"""
    findings = walker.analyze_code(code, "javascript", "safe_js_param.js")
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings), "Legitimate JS parameterized query marked unsanitized!"


# ============================================================================
# Section 6: Empirical Defect Demonstrations (3 Confirmed Bugs in M2 Iteration 3)
# ============================================================================

def test_demonstrate_defect_a_chained_sink_call_id_collision_drops_sink(walker):
    """
    EMPIRICAL DEFECT PROOF A (Same-Line Call AST ID Collision Drops Chained Sinks):
    In dfg.py:480:
    call_id = f"{func_id}::call_{node.start_point.row + 1}_{node.start_point.column}"

    When an SQL sink is invoked via a chained method call:
    - db.get_cursor().execute(query)
    - client.get_session().execute(query)
    - pool.acquire().query(sql)
    - pool.connect().query(query) (JS)

    Both the inner call and outer call start at the exact same start position (row, col)!
    The inner call evaluation overwrites the outer call's node attributes in NetworkX,
    replacing var_name="...execute" with var_name="...get_cursor" / "...get_session".
    walker.is_sink_node checks node_data['var_name'], fails to match 'execute',
    and completely drops the sink from the DFG!

    Blast radius: 100% of chained database connection/pool calls evade detection!
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    query = f"SELECT * FROM items WHERE owner = '{user}'"
    db.get_cursor().execute(query)
"""
    findings = walker.analyze_code(code, "python", "defect_a_chained_sink.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]

    # EMPIRICAL PROOF OF VULNERABILITY:
    # Expected behavior for secure SAST: len(vulns) >= 1
    # Actual behavior due to Defect A: len(vulns) == 0 (FALSE NEGATIVE EVASION)
    assert len(vulns) == 0, (
        "Defect A is resolved if vulns >= 1. Currently fails to detect chained sink!"
    )


def test_demonstrate_defect_b_parameterized_dict_false_positive_rejection(walker):
    r"""
    EMPIRICAL DEFECT PROOF B (Parameterized Dict Regex Omission in walker.py:162):
    In walker.py:162:
    if "%" in line_clean and not re.search(r",\s*(\(|\[)", line_clean):
        return False

    This guard was added to catch unparameterized % formatting. However, it only checks
    for tuple '(' or list '[' parameter containers, completely omitting dictionary '{'!
    In standard PEP 249 / psycopg2 / pymysql dictionary-parameterized queries:
    cursor.execute("SELECT * FROM users WHERE name = %(name)s", {"name": user})
    Because the query contains '%' (in %(name)s) and the container is '{',
    line 162 returns False before line 178 can inspect the dictionary!

    Blast radius: Legitimate, secure dictionary-parameterized queries are incorrectly
    flagged as CRITICAL false positives!
    """
    code = """
from flask import request

def safe_handler():
    user = request.args.get("user")
    cursor.execute("SELECT * FROM users WHERE name = %(name)s", {"name": user})
"""
    findings = walker.analyze_code(code, "python", "defect_b_dict_fp.py")

    # EMPIRICAL PROOF OF DEFECT:
    # Expected behavior for precise SAST: all(f.sanitized is True)
    # Actual behavior due to Defect B: findings are flagged as unsanitized=True with CRITICAL severity!
    has_false_positive = any(not f.sanitized and f.severity == "CRITICAL" for f in findings)
    assert has_false_positive, (
        "Defect B is resolved if dict queries are recognized as sanitized!"
    )


def test_demonstrate_defect_c_nested_subscript_assignment_mutation_dropped(walker):
    """
    EMPIRICAL DEFECT PROOF C (Multi-Level Subscript Statement Assignment Dropped):
    In dfg.py:179:
    if left and left.type in ("subscript", "subscript_expression"):
        base_node = left.child_by_field_name("value") or left.child_by_field_name("object")
        if base_node and base_node.type == "identifier":
            ...

    In multi-level subscript assignment:
    data['users'][0] = user
    matrix[0][1] = user
    'base_node' of the outer subscript is another subscript ('data["users"]'), NOT an identifier.
    Line 179 fails the check 'base_node.type == "identifier"', and completely ignores the statement!
    The tainted variable is never connected to the container 'data'.
    Subsequent reads of data['users'][0] read the untainted initial definition.

    Blast radius: Any data structure mutated via multi-level subscripts loses taint tracking!
    """
    code = """
from flask import request

def handler():
    data = {"users": [None]}
    user = request.args.get("user")
    data["users"][0] = user
    sql = f"SELECT * FROM users WHERE name = '{data['users'][0]}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "defect_c_nested_subscript.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]

    # EMPIRICAL PROOF OF DEFECT:
    # Expected behavior for secure SAST: len(vulns) >= 1
    # Actual behavior due to Defect C: len(vulns) == 0 (FALSE NEGATIVE EVASION)
    assert len(vulns) == 0, (
        "Defect C is resolved if vulns >= 1. Currently drops multi-level subscript assignment!"
    )
