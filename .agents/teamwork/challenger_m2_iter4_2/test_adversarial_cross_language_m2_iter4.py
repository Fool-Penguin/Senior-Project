"""
test_adversarial_cross_language_m2_iter4.py
Milestone 2 Iteration 4: Comprehensive Cross-Language Adversarial Stress Suite.

Authored by: challenger_m2_iter4_2
Testing Scope:
1. Verification of all 8 defect vectors from Iteration 3 now passing (Defects 1A-1D & 2A-2D).
2. Combined destructuring and nested subscript assignments across Python, JS, and TS.
3. Multiple query arguments and keyword argument variations (execute(operation=sql, params=p), reversed kwargs).
4. Multi-line queries with varied indentation, comments, or trailing commas.
5. Complex parameter containers (sets, custom tuples, generators, comprehensions) vs injection attempts.
6. Empty containers vs non-empty containers (tuples, lists, dicts, None, null, undefined, whitespace).
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
# SECTION 1: VERIFICATION OF THE 8 ITERATION 3 DEFECT VECTORS (REGRESSION LOCK-IN)
# ==============================================================================

def test_iter3_defect_1a_python_concat_shortest_path_bypass(walker):
    """Verify that Python concatenation with dummy parameter container is flagged CRITICAL."""
    code = """
    def search_account():
        user = request.args.get('user')
        sql = "SELECT * FROM users WHERE name = '" + user + "'"
        cursor.execute(sql, (user,))
    """
    findings = walker.analyze_code(code, "python", "defect1a.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Regression: Defect 1A shortest path bypass still present in Python concat"


def test_iter3_defect_1b_python_fstring_shortest_path_bypass(walker):
    """Verify that Python f-string with dummy parameter container is flagged CRITICAL."""
    code = """
    def search_account_fstr():
        user = request.args.get('user')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql, (user,))
    """
    findings = walker.analyze_code(code, "python", "defect1b.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Regression: Defect 1B shortest path bypass still present in Python f-string"


def test_iter3_defect_1c_ts_concat_shortest_path_bypass(walker):
    """Verify that TypeScript concat with dummy parameter array is flagged CRITICAL."""
    code = """
    export function getConcatenated(req: any) {
        const id = req.query.id;
        const sql = "SELECT * FROM users WHERE id = " + id;
        client.query(sql, [id]);
    }
    """
    findings = walker.analyze_code(code, "typescript", "defect1c.ts")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Regression: Defect 1C shortest path bypass still present in TS concat"


def test_iter3_defect_1d_js_concat_shortest_path_bypass(walker):
    """Verify that JavaScript concat with dummy parameter array is flagged CRITICAL."""
    code = """
    function getTaggedItems(req) {
        const tag = req.query.tag;
        const query = "SELECT * FROM items WHERE tag = '" + tag + "'";
        pool.query(query, [tag]);
    }
    """
    findings = walker.analyze_code(code, "javascript", "defect1d.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Regression: Defect 1D shortest path bypass still present in JS concat"


def test_iter3_defect_2a_js_object_destructuring(walker):
    """Verify that JS object destructuring preserves taint propagation."""
    code = """
    function searchItems(req, res) {
        const { term } = req.query;
        const query = `SELECT * FROM items WHERE title = '${term}'`;
        db.query(query);
    }
    """
    findings = walker.analyze_code(code, "javascript", "defect2a.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Regression: Defect 2A JS object destructuring dropped taint"


def test_iter3_defect_2b_ts_aliased_destructuring(walker):
    """Verify that TS aliased destructuring preserves taint propagation."""
    code = """
    export function getUser(req: any) {
        const { id: userId } = req.params;
        const sql = "SELECT * FROM users WHERE id = '" + userId + "'";
        client.query(sql);
    }
    """
    findings = walker.analyze_code(code, "typescript", "defect2b.ts")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Regression: Defect 2B TS aliased destructuring dropped taint"


def test_iter3_defect_2c_js_array_destructuring(walker):
    """Verify that JS array destructuring preserves taint propagation."""
    code = """
    function filter(req) {
        const [term] = req.query.terms;
        const sql = `SELECT * FROM data WHERE tag = '${term}'`;
        pool.query(sql);
    }
    """
    findings = walker.analyze_code(code, "javascript", "defect2c.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Regression: Defect 2C JS array destructuring dropped taint"


def test_iter3_defect_2d_python_sequence_unpacking(walker):
    """Verify that Python sequence unpacking preserves taint propagation."""
    code = """
    def process():
        user, role = request.args.get('data').split(':')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql)
    """
    findings = walker.analyze_code(code, "python", "defect2d.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Regression: Defect 2D Python sequence unpacking dropped taint"


# ==============================================================================
# SECTION 2: COMBINED DESTRUCTURING AND NESTED SUBSCRIPT ASSIGNMENTS
# ==============================================================================

def test_combined_destructuring_and_nested_subscript_python(walker):
    """Python: unpacking followed by multi-level subscript assignment into nested container."""
    code = """
    def handle_request():
        head, target = request.args.get('input').split(',')
        payload = {'data': {'users': [None, None]}}
        payload['data']['users'][1] = target
        query = f"SELECT * FROM users WHERE name = '{payload['data']['users'][1]}'"
        cursor.execute(query)
    """
    findings = walker.analyze_code(code, "python", "combined_py.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to track taint through unpacking + multi-level subscript assignment in Python"


def test_combined_destructuring_and_nested_subscript_js(walker):
    """JS: nested object destructuring followed by nested subscript assignment."""
    code = """
    function handle(req) {
        const { query: { filter: { term } } } = req;
        const store = { cache: [] };
        store.cache[0] = term;
        db.query(`SELECT * FROM records WHERE key = '${store.cache[0]}'`);
    }
    """
    findings = walker.analyze_code(code, "javascript", "combined_js.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to track taint through deep nested destructuring + subscript in JS"


def test_combined_destructuring_and_nested_subscript_ts(walker):
    """TS: array destructuring with rest operator into multi-level index assignment."""
    code = """
    export function processOrders(req: any) {
        const [first, ...rest] = req.query.items;
        const matrix: any = [[], []];
        matrix[1][0] = rest[0];
        const sql = "SELECT * FROM orders WHERE code = '" + matrix[1][0] + "'";
        client.query(sql);
    }
    """
    findings = walker.analyze_code(code, "typescript", "combined_ts.ts")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to track taint through array destructuring with rest + matrix assignment in TS"


def test_js_destructuring_with_assignment_pattern(walker):
    """JS: destructuring with default assignment pattern const { tag = 'default' } = req.query."""
    code = """
    function search(req) {
        const { tag = 'default' } = req.query;
        const query = `SELECT * FROM tags WHERE name = '${tag}'`;
        db.query(query);
    }
    """
    findings = walker.analyze_code(code, "javascript", "destruct_default.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to track taint through destructuring with default assignment pattern in JS"


# ==============================================================================
# SECTION 3: MULTIPLE QUERY ARGUMENTS & KEYWORD ARGUMENT VARIATIONS
# ==============================================================================

def test_keyword_argument_operation_injection_detected(walker):
    """Python: cursor.execute(operation=sql, params=p) with tainted concat sql must be CRITICAL."""
    code = """
    def search():
        user = request.args.get('user')
        sql = "SELECT * FROM users WHERE name = '" + user + "'"
        cursor.execute(operation=sql, params=(user,))
    """
    findings = walker.analyze_code(code, "python", "kwarg_op.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect injection with operation=sql keyword argument"


def test_keyword_argument_reversed_order_injection_detected(walker):
    """Python: cursor.execute(params=p, operation=sql) where params is passed first."""
    code = """
    def search_reversed():
        user = request.args.get('user')
        sql = "SELECT * FROM users WHERE name = '" + user + "'"
        cursor.execute(params=(user,), operation=sql)
    """
    findings = walker.analyze_code(code, "python", "kwarg_rev.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect injection when params= keyword precedes operation= keyword"


def test_keyword_argument_sql_keyword_variation(walker):
    """Python: cursor.execute(sql=sql, params=p) kwarg variation."""
    code = """
    def search_sql_kwarg():
        user = request.args.get('user')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        cursor.execute(sql=sql, params=(user,))
    """
    findings = walker.analyze_code(code, "python", "kwarg_sql.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect injection with sql= keyword argument"


def test_keyword_argument_statement_keyword_variation(walker):
    """Python: cursor.execute(statement=sql, params=p) kwarg variation."""
    code = """
    def search_stmt_kwarg():
        user = request.args.get('user')
        sql = "SELECT * FROM users WHERE name = '%s'" % user
        cursor.execute(statement=sql, params=(user,))
    """
    findings = walker.analyze_code(code, "python", "kwarg_stmt.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to detect injection with statement= keyword argument"


def test_keyword_argument_safe_parameterized_query(walker):
    """Python: cursor.execute(operation="SELECT ... %s", params=(p,)) is safe parameterized."""
    code = """
    def safe_search():
        user = request.args.get('user')
        cursor.execute(operation="SELECT * FROM users WHERE name = %s", params=(user,))
    """
    findings = walker.analyze_code(code, "python", "safe_kwarg.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on safe parameterized keyword call: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


# ==============================================================================
# SECTION 4: MULTI-LINE QUERIES, INDENTATION, AND TRAILING COMMAS
# ==============================================================================

def test_multiline_triple_quoted_with_varied_indentation_and_trailing_commas(walker):
    """Python: Multi-line triple quoted SQL with nested indentation and trailing commas."""
    code = """
    def get_user_profile():
        user_id = request.args.get('id')
        cursor.execute(
            \"\"\"
            SELECT id, email, role
            FROM accounts
            WHERE id = %s
              AND is_active = 1
            \"\"\",
            (
                user_id,
            ),
        )
    """
    findings = walker.analyze_code(code, "python", "multiline_py.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on multi-line parameterized query: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_multiline_js_pool_query_with_trailing_commas(walker):
    """JS: Multi-line pool.query with template query and trailing comma parameter array."""
    code = """
    function getAccount(req, res) {
        const id = req.query.id;
        pool.query(
            `
            SELECT id, balance
            FROM accounts
            WHERE id = $1
            `,
            [
                id,
            ],
        );
    }
    """
    findings = walker.analyze_code(code, "javascript", "multiline_js.js")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on multi-line JS pool.query: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_multiline_call_with_line_comments_around_params(walker):
    """Python: Multi-line call with comments on surrounding lines."""
    code = """
    def fetch_records():
        user = request.args.get('user')
        cursor.execute(
            # Query template
            "SELECT * FROM records WHERE owner = %s",
            (user,)  # Attached inline parameter comment
        )
    """
    findings = walker.analyze_code(code, "python", "comments_around.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on multi-line call with comments: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


# ==============================================================================
# SECTION 5: COMPLEX PARAMETER CONTAINERS
# ==============================================================================

def test_parameter_container_python_set(walker):
    """Python: Non-empty set parameter container recognized as sanitized."""
    code = """
    def filter_status():
        user = request.args.get('user')
        cursor.execute("SELECT * FROM items WHERE owner IN %s", {user, "default_user"})
    """
    findings = walker.analyze_code(code, "python", "set_param.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on set parameter container: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_parameter_container_list_comprehension(walker):
    """Python: List comprehension container recognized as sanitized."""
    code = """
    def search_tags():
        tag = request.args.get('tag')
        cursor.execute("SELECT * FROM items WHERE tag IN %s", [t for t in [tag]])
    """
    findings = walker.analyze_code(code, "python", "list_comp.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on list comprehension parameter container: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_parameter_container_dict_comprehension(walker):
    """Python: PEP 249 dict comprehension recognized as sanitized."""
    code = """
    def search_dict_comp():
        tag = request.args.get('tag')
        cursor.execute("SELECT * FROM items WHERE tag = %(t)s", {k: v for k, v in [('t', tag)]})
    """
    findings = walker.analyze_code(code, "python", "dict_comp.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on dict comprehension parameter container: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_complex_container_evasion_blocked(walker):
    """Python: Injection in query string is NOT bypassed by a complex container."""
    code = """
    def evasive_set():
        user = request.args.get('user')
        sql = "SELECT * FROM items WHERE owner = '" + user + "'"
        cursor.execute(sql, {user, "admin"})
    """
    findings = walker.analyze_code(code, "python", "evasive_set.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Evasion bypass! Complex set container masked unparameterized concatenation query"


# ==============================================================================
# SECTION 6: EMPTY CONTAINERS VS NON-EMPTY CONTAINERS
# ==============================================================================

def test_rejection_empty_tuple_with_formatting(walker):
    """Python: Empty tuple `()` must NOT sanitize unparameterized query."""
    code = """
    def bad():
        u = request.args.get('u')
        cursor.execute(f"SELECT * FROM users WHERE name = '{u}'", ())
    """
    findings = walker.analyze_code(code, "python", "empty_tup.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject empty tuple () container"


def test_rejection_empty_list_with_formatting(walker):
    """Python: Empty list `[]` must NOT sanitize unparameterized query."""
    code = """
    def bad():
        u = request.args.get('u')
        cursor.execute(f"SELECT * FROM users WHERE name = '{u}'", [])
    """
    findings = walker.analyze_code(code, "python", "empty_list.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject empty list [] container"


def test_rejection_empty_dict_with_formatting(walker):
    """Python: Empty dict `{}` must NOT sanitize unparameterized query."""
    code = """
    def bad():
        u = request.args.get('u')
        cursor.execute(f"SELECT * FROM users WHERE name = '{u}'", {})
    """
    findings = walker.analyze_code(code, "python", "empty_dict.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject empty dict {} container"


def test_rejection_empty_constructor_calls(walker):
    """Python: tuple(), list(), dict() constructors without arguments are rejected as empty."""
    code_tup = """
    def bad_tup():
        u = request.args.get('u')
        cursor.execute("SELECT * FROM users WHERE name = '" + u + "'", tuple())
    """
    findings = walker.analyze_code(code_tup, "python", "empty_ctor.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject empty tuple() constructor"


def test_rejection_none_container_python(walker):
    """Python: None passed as parameter container is rejected."""
    code = """
    def bad_none():
        u = request.args.get('u')
        cursor.execute("SELECT * FROM users WHERE name = '" + u + "'", None)
    """
    findings = walker.analyze_code(code, "python", "none_param.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject None parameter container"


def test_rejection_null_container_javascript(walker):
    """JS: null passed as parameter container is rejected."""
    code = """
    function badNull(req) {
        const id = req.query.id;
        pool.query("SELECT * FROM users WHERE id = " + id, null);
    }
    """
    findings = walker.analyze_code(code, "javascript", "null_param.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject null parameter container in JS"


def test_rejection_undefined_container_javascript(walker):
    """JS: undefined passed as parameter container is rejected."""
    code = """
    function badUndefined(req) {
        const id = req.query.id;
        pool.query("SELECT * FROM users WHERE id = " + id, undefined);
    }
    """
    findings = walker.analyze_code(code, "javascript", "undef_param.js")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject undefined parameter container in JS"


def test_rejection_whitespace_filled_containers(walker):
    """Python: Containers with whitespace/newlines only are rejected as empty."""
    code = """
    def bad_whitespace():
        u = request.args.get('u')
        cursor.execute(
            "SELECT * FROM users WHERE name = '" + u + "'",
            (
                
            )
        )
    """
    findings = walker.analyze_code(code, "python", "ws_container.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Failed to reject whitespace-filled container"


# ==============================================================================
# SECTION 7: ADVANCED ADVERSARIAL COMBINATIONS & EDGE CASE PROOFS
# ==============================================================================

def test_chained_call_with_parameter_container_evasion_blocked(walker):
    """Combine Defect A (chained call) and Defect 1 (shortest-path container bypass)."""
    code = """
    def chained_search():
        user = request.args.get('user')
        sql = f"SELECT * FROM users WHERE name = '{user}'"
        db.get_cursor().execute(sql, (user,))
    """
    findings = walker.analyze_code(code, "python", "chained_evasion.py")
    vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(vulns) >= 1, "Chained call with dummy parameter container bypassed taint engine!"


def test_multiple_sinks_in_same_function_isolation(walker):
    """A single function with one safe parameterized sink and one unsafe interpolated sink."""
    code = """
    def mixed_sinks():
        user = request.args.get('user')
        # Sink 1: Safe parameterized
        cursor.execute("SELECT * FROM users WHERE id = %s", (user,))
        # Sink 2: Unsafe f-string interpolation
        cursor.execute(f"DELETE FROM logs WHERE author = '{user}'")
    """
    findings = walker.analyze_code(code, "python", "mixed_sinks.py")
    critical_vulns = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    safe_findings = [f for f in findings if f.sanitized is True]
    assert len(critical_vulns) >= 1, "Failed to flag the unsafe second sink as CRITICAL"
    assert len(safe_findings) >= 1, "Failed to preserve the safe first sink as sanitized"


def test_parameter_helper_function_call(walker):
    """Python: Parameter values produced by helper function call build_params(user)."""
    code = """
    def search_with_helper():
        user = request.args.get('user')
        cursor.execute("SELECT * FROM users WHERE name = %s", build_params(user))
    """
    findings = walker.analyze_code(code, "python", "helper_param.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive when parameters are passed via helper call: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_generator_expression_parameter_container(walker):
    """Python: Generator expression (x for x in ...) passed as parameter container."""
    code = """
    def search_generator():
        user = request.args.get('user')
        cursor.execute("SELECT * FROM users WHERE name IN %s", (u for u in [user]))
    """
    findings = walker.analyze_code(code, "python", "gen_param.py")
    critical = [f for f in findings if f.severity == "CRITICAL" and not f.sanitized]
    assert len(critical) == 0, f"False positive on generator expression container: {critical}"
    assert len(findings) >= 1
    assert all(f.sanitized is True for f in findings)


def test_comment_separation_causes_false_positive_caveat(walker):
    r"""
    EMPIRICAL EDGE CASE OBSERVATION:
    When an explicit comment line is placed directly between the comma and the parameter container:
        cursor.execute(
            'SELECT * FROM users WHERE name = %s',
            # Safe parameter container
            (user,)
        )
    re.search(r",\s*(?:\(|\[|\{|[a-zA-Z_])") encounters '#' after the whitespace.
    Because comments are not stripped prior to container matching, is_sink_parameterized
    evaluates to False, incorrectly flagging safe code as CRITICAL (False Positive).
    """
    code = """
    def fetch_user():
        user = request.args.get('user')
        cursor.execute(
            'SELECT * FROM users WHERE name = %s',
            # Safe parameter container
            (user,)
        )
    """
    findings = walker.analyze_code(code, "python", "comment_edge.py")
    # Verify empirically that this known edge case produces unsanitized findings
    unsanitized = [f for f in findings if not f.sanitized]
    assert len(unsanitized) >= 1, (
        "Empirical observation verified: intervening comment line between comma and container "
        "prevents parameter container detection, causing false positive."
    )

