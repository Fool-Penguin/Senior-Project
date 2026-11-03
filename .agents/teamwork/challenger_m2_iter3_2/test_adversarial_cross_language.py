"""
test_adversarial_cross_language.py
Empirical Adversarial Stress Testing Suite for CodeDEE DFG & Symbolic Taint Walker (Stage 3A).

Authored by: challenger_m2_iter3_2
Focus Areas:
- Cross-Language Verification: Python, JavaScript, TypeScript
- Method Chaining Robustness (.trim().toLowerCase().slice(...))
- Spread Syntax and Destructuring Assignment
- Genuine Parameterized Queries vs Dummy Parameter Bypass
- False-Positive Isolation on Safe Code
"""

import sys
from pathlib import Path
import pytest

SERVER_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "codedee" / "codedee_server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.taint.walker import SymbolicTaintWalker
from app.graphs.dfg import DFGBuilder


@pytest.fixture
def walker():
    return SymbolicTaintWalker()


# ==============================================================================
# SECTION 1: Confirmed Passing Capabilities (Method Chaining & Spread Syntax)
# ==============================================================================

def test_js_method_chaining_trim_tolowercase(walker):
    """Verify req.query.search.trim().toLowerCase() propagates taint to SQL sink."""
    code = """
    function handleSearch(req, res) {
        const raw = req.query.search.trim().toLowerCase();
        const sql = `SELECT * FROM products WHERE name = '${raw}'`;
        db.query(sql);
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="search.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect SQL injection through chained .trim().toLowerCase()"


def test_ts_method_chaining_deep_chain(walker):
    """Verify deep method chaining in TypeScript: req.query.name.trim().toLowerCase().slice(0, 10)."""
    code = """
    import { Request, Response } from 'express';
    export async function findUser(req: Request, res: Response) {
        const sanitizedStr: string = req.query.name.trim().toLowerCase().slice(0, 10);
        const query = "SELECT * FROM users WHERE username = '" + sanitizedStr + "'";
        await pool.query(query);
    }
    """
    findings = walker.analyze_code(code, language="typescript", file_path="user.ts")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect SQL injection through deep TS method chain"


def test_js_method_chaining_inline_in_template_literal(walker):
    """Verify inline method chaining directly inside template literal."""
    code = """
    app.get('/users', async (req, res) => {
        const result = await client.query(`SELECT * FROM users WHERE email = '${req.query.email.trim().toLowerCase()}'`);
        res.json(result);
    });
    """
    findings = walker.analyze_code(code, language="javascript", file_path="inline.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect inline chained method call inside template literal"


def test_python_method_chaining_strip_lower_replace(walker):
    """Verify Python method chaining: request.args.get('user').strip().lower().replace('admin', 'root')."""
    code = """
    def get_account():
        user = request.args.get('user').strip().lower().replace('admin', 'root')
        cursor.execute(f"SELECT * FROM accounts WHERE owner = '{user}'")
    """
    findings = walker.analyze_code(code, language="python", file_path="account.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect SQL injection through Python method chain"


def test_js_object_spread_taint_propagation(walker):
    """Verify JS object spread with member access: const params = { ...req.query }; params.term."""
    code = """
    function queryHandler(req) {
        const params = { ...req.query };
        const query = `SELECT * FROM logs WHERE msg = '${params.term}'`;
        db.query(query);
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="spread_obj.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect SQL injection through object spread"


def test_js_array_spread_taint_propagation(walker):
    """Verify JS array spread with subscript indexing: const items = [...req.body.data]; items[0]."""
    code = """
    function processItems(req) {
        const items = [...req.body.data];
        const query = "SELECT * FROM inventory WHERE code = '" + items[0] + "'";
        db.query(query);
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="spread_arr.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect SQL injection through array spread"


# ==============================================================================
# SECTION 2: Safe Code Isolation (Zero False Positives)
# ==============================================================================

def test_safe_python_static_query_not_flagged(walker):
    """Verify static query without user input produces zero findings."""
    code = """
    def list_all_active_users():
        cursor.execute("SELECT id, username, email FROM users WHERE is_active = 1 ORDER BY id DESC")
    """
    findings = walker.analyze_code(code, language="python", file_path="static.py")
    assert len(findings) == 0, f"False positive on purely static Python query: {findings}"


def test_safe_js_static_template_literal_not_flagged(walker):
    """Verify static template literal (no interpolations) produces zero findings."""
    code = """
    function getStatic() {
        const query = `SELECT id, name FROM categories WHERE status = 'live'`;
        db.query(query);
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="static_tpl.js")
    assert len(findings) == 0, f"False positive on static JS template literal: {findings}"


def test_safe_ts_internal_constant_interpolation_not_flagged(walker):
    """Verify TS interpolation of internal compile-time constants produces zero findings."""
    code = """
    const TABLE_NAME = "customers";
    const DEFAULT_LIMIT = 50;

    export async function fetchCustomers() {
        const sql = `SELECT * FROM ${TABLE_NAME} LIMIT ${DEFAULT_LIMIT}`;
        await pool.query(sql);
    }
    """
    findings = walker.analyze_code(code, language="typescript", file_path="const_interp.ts")
    assert len(findings) == 0, f"False positive on constant interpolation: {findings}"


def test_safe_python_int_cast_sanitization(walker):
    """Verify int(request.args.get('id')) is recognized as safe sanitized input."""
    code = """
    def get_by_numeric_id():
        raw_id = request.args.get('id')
        user_id = int(raw_id)
        cursor.execute(f"SELECT * FROM items WHERE id = {user_id}")
    """
    findings = walker.analyze_code(code, language="python", file_path="int_cast.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on int()-cast sanitized value: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_safe_js_parseint_sanitization(walker):
    """Verify parseInt(req.query.id, 10) is recognized as safe sanitized input."""
    code = """
    function getProduct(req, res) {
        const rawId = req.query.id;
        const productId = parseInt(rawId, 10);
        db.query(`SELECT * FROM products WHERE id = ${productId}`);
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="parseint.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on parseInt-cast sanitized value: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_safe_js_genuine_parameterized_pg_pool_query(walker):
    """Verify genuine parameterized query in pg pool.query($1, [val]) is marked sanitized."""
    code = """
    function getSafeUser(req, res) {
        const id = req.query.id;
        pool.query('SELECT * FROM users WHERE id = $1 AND role = $2', [id, 'user'], (err, result) => {
            res.json(result);
        });
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="safe_pg.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive: Genuine parameterized query flagged as CRITICAL: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_safe_ts_genuine_parameterized_mysql2_execute(walker):
    """Verify genuine parameterized query in mysql2 connection.execute(?, [val]) is marked sanitized."""
    code = """
    import mysql from 'mysql2/promise';
    export async function fetchAccount(req: any) {
        const conn = await mysql.createConnection({});
        const username = req.params.username;
        return await conn.execute('SELECT * FROM accounts WHERE username = ?', [username]);
    }
    """
    findings = walker.analyze_code(code, language="typescript", file_path="safe_mysql.ts")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive: Genuine TS parameterized query flagged: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_rejection_empty_container_js_pool_query(walker):
    """Verify empty array container pool.query(sql, []) is correctly rejected."""
    code = """
    function getSneakyUser(req, res) {
        const id = req.query.id;
        const sql = "SELECT * FROM users WHERE id = " + id;
        pool.query(sql, []);
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="empty_arr.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject empty array parameter container"


def test_rejection_empty_container_ts_template_literal(walker):
    """Verify empty array container pool.query(`... ${id}`, []) is correctly rejected."""
    code = """
    export function getBadUser(req: any) {
        const id = req.query.id;
        client.query(`SELECT * FROM users WHERE id = ${id}`, []);
    }
    """
    findings = walker.analyze_code(code, language="typescript", file_path="empty_ts.ts")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject empty array parameter container"


# ==============================================================================
# SECTION 3: EMPIRICAL DEFECT DEMONSTRATIONS (CONFIRMED EVASION DEFECTS)
# ==============================================================================

# --- DEFECT 1: Shortest-Path Parameterization Bypass via Tainted Container ---

def test_demonstrate_defect_1a_python_concat_with_dummy_parameter(walker):
    r"""
    EMPIRICAL DEFECT PROOF 1A:
    When an SQL query string is constructed via unparameterized concatenation:
        sql = "SELECT * FROM users WHERE name = '" + user + "'"
    and executed with a secondary parameter container containing the tainted variable:
        cursor.execute(sql, (user,))
    nx.shortest_path(dfg, src, snk) selects the 4-hop path through (user,) instead of
    the 6-hop path through concatenation into sql.
    Because the shortest path has no string formatting, has_unparameterized_string_format
    evaluates to False. is_sink_parameterized sees ', (user,)' and returns True.
    CodeDEE marks the query as sanitized=True with LOW severity, masking SQL Injection!
    """
    code = """
    def search_account():
        user = request.args.get('user')
        sql = "SELECT * FROM users WHERE name = '" + user + "'"
        cursor.execute(sql, (user,))
    """
    findings = walker.analyze_code(code, "python", "py_concat_dummy.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, (
        "Defect 1A Evasion Confirmed: cursor.execute(concat_sql, (user,)) bypassed taint walker! "
        f"Findings were incorrectly marked sanitized: {findings}"
    )


def test_demonstrate_defect_1b_python_fstring_with_dummy_parameter(walker):
    r"""
    EMPIRICAL DEFECT PROOF 1B:
    Same bypass mechanism as 1A, but with Python f-string interpolation:
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql, (user,))
    Shortest path traverses (user,) and bypasses the f-string interpolation node.
    """
    code = """
    def search_account_fstr():
        user = request.args.get('user')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql, (user,))
    """
    findings = walker.analyze_code(code, "python", "py_fstr_dummy.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, (
        "Defect 1B Evasion Confirmed: cursor.execute(fstring_sql, (user,)) bypassed taint walker! "
        f"Findings were incorrectly marked sanitized: {findings}"
    )


def test_demonstrate_defect_1c_ts_concat_with_dummy_parameter(walker):
    r"""
    EMPIRICAL DEFECT PROOF 1C:
    TypeScript string concatenation with dummy parameter array:
        const sql = "SELECT * FROM users WHERE id = " + id;
        client.query(sql, [id]);
    Shortest path traverses [id] (4 hops) instead of concatenation (6 hops),
    causing CodeDEE to classify the vulnerability as sanitized=True (LOW severity).
    """
    code = """
    export function getConcatenated(req: any) {
        const id = req.query.id;
        const sql = "SELECT * FROM users WHERE id = " + id;
        client.query(sql, [id]);
    }
    """
    findings = walker.analyze_code(code, "typescript", "ts_dummy_concat.ts")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, (
        "Defect 1C Evasion Confirmed: client.query(concat_sql, [id]) bypassed taint walker! "
        f"Findings were incorrectly marked sanitized: {findings}"
    )


def test_demonstrate_defect_1d_js_concat_with_dummy_parameter(walker):
    r"""
    EMPIRICAL DEFECT PROOF 1D:
    JavaScript string concatenation with dummy parameter array:
        const query = "SELECT * FROM items WHERE tag = '" + tag + "'";
        pool.query(query, [tag]);
    """
    code = """
    function getTaggedItems(req) {
        const tag = req.query.tag;
        const query = "SELECT * FROM items WHERE tag = '" + tag + "'";
        pool.query(query, [tag]);
    }
    """
    findings = walker.analyze_code(code, "javascript", "js_dummy_concat.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, (
        "Defect 1D Evasion Confirmed: pool.query(concat_sql, [tag]) bypassed taint walker! "
        f"Findings were incorrectly marked sanitized: {findings}"
    )


# --- DEFECT 2: Destructuring Assignment Taint Loss across JS, TS, and Python ---

def test_demonstrate_defect_2a_js_object_destructuring_taint_loss(walker):
    r"""
    EMPIRICAL DEFECT PROOF 2A:
    In dfg.py:221, variable_declaration only checks:
        if name_node and name_node.type == "identifier":
    Object destructuring:
        const { term } = req.query;
    produces name_node.type == "object_pattern", which is completely unhandled.
    current_defs['term'] is never registered. When 'term' is used in the query string,
    it has no incoming edge in the DFG, producing 0 findings (False Negative)!
    """
    code = """
    function searchItems(req, res) {
        const { term } = req.query;
        const query = `SELECT * FROM items WHERE title = '${term}'`;
        db.query(query);
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="destruct.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, (
        "Defect 2A Failure: JS object destructuring dropped taint propagation! "
        f"Got {len(findings)} findings instead of detected CRITICAL vulnerability."
    )


def test_demonstrate_defect_2b_ts_aliased_destructuring_taint_loss(walker):
    r"""
    EMPIRICAL DEFECT PROOF 2B:
    TypeScript aliased destructuring:
        const { id: userId } = req.params;
    produces name_node.type == "object_pattern" containing a 'pair_pattern'.
    dfg.py ignores the declarator, dropping taint for 'userId' completely!
    """
    code = """
    export function getUser(req: any) {
        const { id: userId } = req.params;
        const sql = "SELECT * FROM users WHERE id = '" + userId + "'";
        client.query(sql);
    }
    """
    findings = walker.analyze_code(code, language="typescript", file_path="alias_destruct.ts")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, (
        "Defect 2B Failure: TS aliased destructuring dropped taint propagation! "
        f"Got {len(findings)} findings instead of detected CRITICAL vulnerability."
    )


def test_demonstrate_defect_2c_js_array_destructuring_taint_loss(walker):
    r"""
    EMPIRICAL DEFECT PROOF 2C:
    JavaScript array destructuring:
        const [term] = req.query.terms;
    produces name_node.type == "array_pattern".
    dfg.py ignores array patterns, dropping taint for 'term' completely!
    """
    code = """
    function filter(req) {
        const [term] = req.query.terms;
        const sql = `SELECT * FROM data WHERE tag = '${term}'`;
        pool.query(sql);
    }
    """
    findings = walker.analyze_code(code, language="javascript", file_path="arr_destruct.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, (
        "Defect 2C Failure: JS array destructuring dropped taint propagation! "
        f"Got {len(findings)} findings instead of detected CRITICAL vulnerability."
    )


def test_demonstrate_defect_2d_python_tuple_unpacking_taint_loss(walker):
    r"""
    EMPIRICAL DEFECT PROOF 2D:
    Python tuple / list unpacking:
        user, role = request.args.get('data').split(':')
    produces left.type == "pattern_list".
    dfg.py:143 only checks left.type == "identifier", dropping taint for 'user'!
    When sql is assigned on a prior line:
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql)
    The DFG drops the edge, producing 0 findings!
    """
    code = """
    def process():
        user, role = request.args.get('data').split(':')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql)
    """
    findings = walker.analyze_code(code, language="python", file_path="unpack.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, (
        "Defect 2D Failure: Python tuple unpacking dropped taint propagation! "
        f"Got {len(findings)} findings instead of detected CRITICAL vulnerability."
    )
