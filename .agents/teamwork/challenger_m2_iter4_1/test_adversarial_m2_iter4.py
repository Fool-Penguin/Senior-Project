"""
test_adversarial_m2_iter4.py - Empirical Adversarial Challenge Suite for Milestone 2 Iteration 4.

Author: Challenger 1 (critic / specialist)
Target: Static Analysis & Graph Modeling Engine (codedee_server/app/graphs/, codedee_server/app/taint/)

Test Dimensions:
1. Deeply chained method invocations (3+ chains, cross-language)
2. Deeply nested subscript assignments and reads
3. Complex destructuring patterns (nested object/array, aliasing, defaults, rest/splat in JS/TS & Python)
4. Complex query argument formatting (multi-binop, format methods, nested interpolations, evasion attempts)
5. False positive checks (legitimate parameterized queries, PEP 249 dicts, multi-line calls, type casts)
"""

import os
import sys
from pathlib import Path
import pytest
import networkx as nx

# Add codedee_server to sys.path
SERVER_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "codedee" / "codedee_server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.graphs.dfg import DFGBuilder
from app.graphs.call_graph import CallGraphBuilder
from app.taint.walker import SymbolicTaintWalker
from app.parser.cst_manager import CSTParserManager


@pytest.fixture
def taint_walker() -> SymbolicTaintWalker:
    return SymbolicTaintWalker()


@pytest.fixture
def dfg_builder() -> DFGBuilder:
    return DFGBuilder()


# ==============================================================================
# SECTION 1: Deeply Chained Method Invocations (3+ Chains)
# ==============================================================================

class TestDeeplyChainedMethodInvocations:
    """
    Stress-test chained method calls (>= 3 chains) to ensure:
    - Node IDs do not collide across nested call expressions sharing start coordinates.
    - Receiver and argument edges are correctly structured without self-loops.
    - Taint propagates from source through deeply chained database sinks.
    """

    def test_python_4_chain_method_invocation_vulnerable(self, taint_walker):
        """Python: client.get_pool().acquire().get_connection().query(f'SELECT ... {user}')"""
        code = (
            "def handler(request):\n"
            "    user = request.args.get('user')\n"
            "    res = client.get_pool().acquire().get_connection().query(f\"SELECT * FROM users WHERE name = '{user}'\")\n"
            "    return res\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="chain4.py")
        assert len(findings) >= 1, "Failed to detect injection through 4-chain method call"
        f = findings[0]
        assert f.severity == "CRITICAL"
        assert not f.sanitized
        assert "query" in f.sink_node["expression"]

    def test_python_5_chain_method_invocation_concat(self, taint_walker):
        """Python: db.cluster().primary().get_session().factory().execute('SELECT ... ' + user)"""
        code = (
            "def execute_task(request):\n"
            "    user = request.args.get('user')\n"
            "    db.cluster().primary().get_session().factory().execute('SELECT * FROM audit WHERE u = ' + user)\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="chain5.py")
        assert len(findings) >= 1, "Failed to detect injection through 5-chain method call with concat"
        f = findings[0]
        assert f.severity == "CRITICAL"
        assert not f.sanitized
        assert "execute" in f.sink_node["expression"]

    def test_python_chained_calls_intermediate_args(self, taint_walker):
        """Python: pool.get_conn(timeout=5).cursor(buffered=True).execute(f'SELECT ... {user}')"""
        code = (
            "def fetch(request):\n"
            "    user = request.args.get('user')\n"
            "    pool.get_conn(timeout=5).cursor(buffered=True).execute(f\"SELECT * FROM data WHERE x = '{user}'\")\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="chain_args.py")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"

    def test_python_chained_calls_dfg_no_self_loops_or_collisions(self, dfg_builder):
        """Verify DFG node uniqueness and absence of self-loops in 4-chain call."""
        code = (
            "def test_chain():\n"
            "    a = client.get_pool().acquire().get_connection().query('safe')\n"
        )
        dfg = dfg_builder.build_for_code(code, language="python", file_path="chain_dfg.py")
        # Ensure no self loops exist anywhere in the graph
        self_loops = [u for u, v in dfg.edges() if u == v]
        assert len(self_loops) == 0, f"Found self loops in DFG: {self_loops}"

        # Verify distinct call nodes were added for each chained level
        call_nodes = [n for n, d in dfg.nodes(data=True) if d.get("node_kind") == "CALL_ARG"]
        assert len(call_nodes) == 4, f"Expected 4 distinct CALL_ARG nodes, got {len(call_nodes)}: {call_nodes}"

    def test_javascript_4_chain_method_invocation_vulnerable(self, taint_walker):
        """JS: client.getPool().acquire().getConnection().query(`SELECT ... ${user}`)"""
        code = (
            "async function handle(req, res) {\n"
            "    const user = req.query.user;\n"
            "    const rows = await client.getPool().acquire().getConnection().query(`SELECT * FROM users WHERE name = '${user}'`);\n"
            "    res.json(rows);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="chain_js.js")
        assert len(findings) >= 1
        f = findings[0]
        assert f.severity == "CRITICAL"
        assert not f.sanitized

    def test_typescript_5_chain_typeorm_vulnerable(self, taint_walker):
        """TS: AppDataSource.createQueryRunner().connect().startTransaction().manager.query(`SELECT ... ${id}`)"""
        code = (
            "import { Request, Response } from 'express';\n"
            "export async function runQuery(req: Request, res: Response) {\n"
            "    const id: string = req.query.id as string;\n"
            "    await AppDataSource.createQueryRunner().connect().startTransaction().manager.query(`SELECT * FROM acc WHERE id = '${id}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="typescript", file_path="chain_ts.ts")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"

    def test_chained_call_properly_parameterized_safe(self, taint_walker):
        """Chained call with parameterized query must NOT be flagged as CRITICAL."""
        code = (
            "def handler(request):\n"
            "    user = request.args.get('user')\n"
            "    res = client.get_pool().acquire().get_connection().query(\"SELECT * FROM users WHERE name = %s\", (user,))\n"
            "    return res\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="chain_safe.py")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive: parameterized chained query flagged CRITICAL: {criticals}"
        if findings:
            assert findings[0].sanitized is True


# ==============================================================================
# SECTION 2: Deeply Nested Subscript Assignments and Reads
# ==============================================================================

class TestDeeplyNestedSubscripts:
    """
    Stress-test nested subscript / dictionary mutation and extraction:
    - Multi-level assignments: a[0]['b'][1]['c'] = user
    - Multi-level reads: cursor.execute("SELECT " + data['users'][0]['info']['id'])
    - Container mutation unwinding to root identifier.
    """

    def test_python_4_level_nested_subscript_assignment(self, taint_walker):
        """Python: data['payload'][0]['metadata']['user'] = request.args.get('user')"""
        code = (
            "def process(request):\n"
            "    data = {'payload': [{'metadata': {}}]}\n"
            "    data['payload'][0]['metadata']['user'] = request.args.get('user')\n"
            "    sql = f\"SELECT * FROM records WHERE u = '{data['payload'][0]['metadata']['user']}'\"\n"
            "    cursor.execute(sql)\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="subscript_4.py")
        assert len(findings) >= 1, "Failed to track taint through 4-level nested subscript assignment"
        f = findings[0]
        assert f.severity == "CRITICAL"
        assert not f.sanitized

    def test_python_5_level_subscript_write_and_concat_read(self, taint_walker):
        """Python: a[0]['b'][1]['c'][2] = user; cursor.execute("SELECT ... " + str(a[0]['b'][1]['c'][2]))"""
        code = (
            "def handle(request):\n"
            "    user = request.args.get('user')\n"
            "    a = {}\n"
            "    a[0]['b'][1]['c'][2] = user\n"
            "    cursor.execute('SELECT * FROM data WHERE val = ' + a[0]['b'][1]['c'][2])\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="subscript_5.py")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"

    def test_javascript_nested_subscript_and_property_access(self, taint_walker):
        """JS: req.body.users[0]['profile'].details[1] = user; db.query(`SELECT ... ${...}`)"""
        code = (
            "function search(req, res) {\n"
            "    const user = req.query.user;\n"
            "    const state = { users: [{ profile: { details: [] } }] };\n"
            "    state.users[0]['profile'].details[1] = user;\n"
            "    db.query(`SELECT * FROM accounts WHERE name = '${state.users[0]['profile'].details[1]}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="subscript_js.js")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"

    def test_typescript_bracket_and_member_nested_access(self, taint_walker):
        """TS: cache['session'][user_key].token = tainted"""
        code = (
            "import { Request, Response } from 'express';\n"
            "export function auth(req: Request, res: Response) {\n"
            "    const input = req.query.term as string;\n"
            "    const cache: any = {};\n"
            "    cache['sessions'][0]['meta'].query = input;\n"
            "    db.query(`SELECT * FROM sessions WHERE q = '${cache['sessions'][0]['meta'].query}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="typescript", file_path="subscript_ts.ts")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"


# ==============================================================================
# SECTION 3: Complex Destructuring Patterns (JS/TS & Python)
# ==============================================================================

class TestComplexDestructuringPatterns:
    """
    Stress-test complex destructuring:
    - JS/TS deeply nested object destructuring (3+ levels)
    - JS/TS destructuring with aliasing
    - JS/TS destructuring with default fallback values
    - JS/TS array destructuring with rest patterns
    - Python sequence unpacking (tuple, list)
    - Python extended iterable unpacking (*rest splat)
    - Python deeply nested tuple unpacking
    """

    def test_js_3_level_nested_object_destructuring(self, taint_walker):
        """JS: const { user: { profile: { address: { street } } } } = req.body;"""
        code = (
            "function lookup(req, res) {\n"
            "    const { user: { profile: { address: { street } } } } = req.body;\n"
            "    db.query(`SELECT * FROM locations WHERE street = '${street}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="destruct_nested_obj.js")
        assert len(findings) >= 1, "Failed to track taint through 3-level nested object destructuring"
        assert findings[0].severity == "CRITICAL"

    def test_js_aliased_and_nested_destructuring(self, taint_walker):
        """JS: const { search: term, filter: { tag: category } } = req.query;"""
        code = (
            "function searchPosts(req, res) {\n"
            "    const { search: term, filter: { tag: category } } = req.query;\n"
            "    client.query(`SELECT * FROM posts WHERE cat = '${category}' AND tag = '${term}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="destruct_alias.js")
        assert len(findings) >= 1, "Failed to track taint through aliased destructuring"
        assert findings[0].severity == "CRITICAL"

    def test_js_destructuring_with_default_values(self, taint_walker):
        """JS: const { query = 'default_search', limit = 10 } = req.query;"""
        code = (
            "function searchItems(req, res) {\n"
            "    const { query = 'default_search', limit = 10 } = req.query;\n"
            "    db.query(`SELECT * FROM items WHERE q = '${query}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="destruct_defaults.js")
        assert len(findings) >= 1, "Failed to track taint through destructuring with default values"
        assert findings[0].severity == "CRITICAL"

    def test_js_array_destructuring_with_rest_pattern(self, taint_walker):
        """JS: const [head, second, ...tail] = req.body.tokens;"""
        code = (
            "function authTokens(req, res) {\n"
            "    const [head, second, ...tail] = req.body.tokens;\n"
            "    db.query(`SELECT * FROM auth WHERE t = '${head}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="destruct_rest.js")
        assert len(findings) >= 1, "Failed to track taint through array destructuring with rest pattern"
        assert findings[0].severity == "CRITICAL"

    def test_js_array_destructuring_rest_variable_used(self, taint_walker):
        """JS: const [head, ...tail] = req.body.tokens; db.query(...tail[0]...)"""
        code = (
            "function authTail(req, res) {\n"
            "    const [head, ...tail] = req.body.tokens;\n"
            "    db.query(`SELECT * FROM auth WHERE t = '${tail[0]}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="destruct_tail.js")
        assert len(findings) >= 1, "Failed to track taint through rest element target"
        assert findings[0].severity == "CRITICAL"

    def test_js_mixed_object_and_array_destructuring(self, taint_walker):
        """JS: const [{ user: { id } }] = req.body.list;"""
        code = (
            "function getFirst(req, res) {\n"
            "    const [{ user: { id } }] = req.body.list;\n"
            "    client.query(`SELECT * FROM users WHERE id = '${id}'`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="destruct_mixed.js")
        assert len(findings) >= 1, "Failed to track taint through mixed object/array destructuring"
        assert findings[0].severity == "CRITICAL"

    def test_python_nested_tuple_unpacking(self, taint_walker):
        """Python: ((x, y), (z, w)) = request.get_coords()"""
        code = (
            "def find_coord(request):\n"
            "    ((x, y), (z, w)) = request.get_coords()\n"
            "    cursor.execute(f\"SELECT * FROM grid WHERE z = '{z}'\")\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="unpack_nested_tuple.py")
        assert len(findings) >= 1, "Failed to track taint through nested tuple unpacking"
        assert findings[0].severity == "CRITICAL"

    def test_python_extended_iterable_unpacking_splat(self, taint_walker):
        """Python: first, *middle, last = request.args['items']"""
        code = (
            "def parse_items(request):\n"
            "    first, *middle, last = request.args['items']\n"
            "    cursor.execute(f\"SELECT * FROM log WHERE last = '{last}'\")\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="unpack_splat.py")
        assert len(findings) >= 1, "Failed to track taint through extended iterable unpacking (*middle)"
        assert findings[0].severity == "CRITICAL"


# ==============================================================================
# SECTION 4: Complex Query Argument Formatting & Evasion Resistance
# ==============================================================================

class TestComplexQueryFormatting:
    """
    Stress-test complex query argument expressions:
    - Multiple binary operator additions (5+ chunks)
    - str.format() method calls with positional and keyword arguments
    - Mixed %-formatting operations
    - Nested f-string interpolation: f"{f'{user}'}"
    - Evasion attempts: tainted query in arg 0 with secondary dummy parameters in arg 1
    """

    def test_python_multiple_binary_operators_vulnerable(self, taint_walker):
        """Python: q = 'SELECT ' + '*' + ' FROM ' + 'users ' + 'WHERE ' + 'name = \\'' + user + '\\'';"""
        code = (
            "def search(request):\n"
            "    user = request.args.get('user')\n"
            "    q = 'SELECT ' + '*' + ' FROM ' + 'users ' + 'WHERE ' + 'name = \\'' + user + '\\''\n"
            "    cursor.execute(q)\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="multi_binop.py")
        assert len(findings) >= 1, "Failed to detect injection built via multiple binary additions"
        assert findings[0].severity == "CRITICAL"

    def test_python_format_method_positional_and_kwargs(self, taint_walker):
        """Python: 'SELECT ... {0} ... {role}'.format(user, role=role)"""
        code = (
            "def query_user(request):\n"
            "    user = request.args.get('user')\n"
            "    role = request.args.get('role')\n"
            "    q = \"SELECT * FROM users WHERE name = '{0}' AND role = '{role}'\".format(user, role=role)\n"
            "    cursor.execute(q)\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="format_method.py")
        assert len(findings) >= 1, "Failed to detect injection via str.format() call"
        assert findings[0].severity == "CRITICAL"

    def test_python_format_method_chained_on_literal(self, taint_walker):
        """Python: cursor.execute('SELECT ... {}'.format(user))"""
        code = (
            "def lookup(request):\n"
            "    user = request.args.get('user')\n"
            "    cursor.execute('SELECT * FROM data WHERE x = {}'.format(user))\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="format_chained.py")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"

    def test_python_nested_fstring_interpolation(self, taint_walker):
        """Python: cursor.execute(f"SELECT * FROM t WHERE name = '{f'{prefix}_{user}'}'")"""
        code = (
            "def nested_fstr(request):\n"
            "    user = request.args.get('user')\n"
            "    prefix = 'USR'\n"
            "    cursor.execute(f\"SELECT * FROM t WHERE name = '{f'{prefix}_{user}'}'\")\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="nested_fstr.py")
        assert len(findings) >= 1, "Failed to detect injection in nested f-string"
        assert findings[0].severity == "CRITICAL"

    def test_evasion_python_fstring_with_dummy_tuple_parameter(self, taint_walker):
        """Evasion: cursor.execute(f'SELECT ... {user}', (user,)) must REMAIN CRITICAL."""
        code = (
            "def login(request):\n"
            "    user = request.args.get('user')\n"
            "    cursor.execute(f\"SELECT * FROM users WHERE name = '{user}'\", (user,))\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="evasion_py_fstr.py")
        assert len(findings) >= 1
        f = findings[0]
        assert f.severity == "CRITICAL", f"Evasion succeeded! Severity was downgraded to {f.severity}"
        assert not f.sanitized

    def test_evasion_python_concat_with_dummy_list_parameter(self, taint_walker):
        """Evasion: cursor.execute('SELECT ... ' + user, [user]) must REMAIN CRITICAL."""
        code = (
            "def login(request):\n"
            "    user = request.args.get('user')\n"
            "    cursor.execute('SELECT * FROM users WHERE name = ' + user, [user])\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="evasion_py_concat.py")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"
        assert not findings[0].sanitized

    def test_evasion_js_template_with_dummy_array_parameter(self, taint_walker):
        """Evasion: db.query(`SELECT ... ${user}`, [user]) must REMAIN CRITICAL."""
        code = (
            "function query(req, res) {\n"
            "    const user = req.query.user;\n"
            "    db.query(`SELECT * FROM users WHERE name = '${user}'`, [user]);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="evasion_js_tpl.js")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"
        assert not findings[0].sanitized

    def test_evasion_ts_concat_with_dummy_parameter(self, taint_walker):
        """Evasion: client.query('SELECT ... ' + user, [user]) must REMAIN CRITICAL."""
        code = (
            "import { Request, Response } from 'express';\n"
            "export function query(req: Request, res: Response) {\n"
            "    const user = req.query.user as string;\n"
            "    client.query('SELECT * FROM users WHERE name = ' + user, [user]);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="typescript", file_path="evasion_ts_concat.ts")
        assert len(findings) >= 1
        assert findings[0].severity == "CRITICAL"
        assert not findings[0].sanitized


# ==============================================================================
# SECTION 5: False Positive Checks (Precision & Non-Regression)
# ==============================================================================

class TestFalsePositiveResistance:
    """
    Ensure legitimate parameterized queries and safe type-casting are NEVER
    flagged as CRITICAL vulnerabilities:
    - Parameterized queries with tuples, lists, dictionaries (PEP 249)
    - Multi-line sink calls
    - Explicit integer type casts (int(), parseInt(), Number())
    - Explicit float type casts (float())
    """

    def test_safe_python_parameterized_tuple(self, taint_walker):
        """Python: cursor.execute('SELECT * FROM users WHERE name = %s', (user,))"""
        code = (
            "def get_user(request):\n"
            "    user = request.args.get('user')\n"
            "    cursor.execute('SELECT * FROM users WHERE name = %s', (user,))\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="safe_tuple.py")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive on parameterized tuple: {criticals}"
        if findings:
            assert findings[0].sanitized is True

    def test_safe_python_parameterized_list(self, taint_walker):
        """Python: cursor.execute('SELECT * FROM users WHERE name = ?', [user])"""
        code = (
            "def get_user(request):\n"
            "    user = request.args.get('user')\n"
            "    cursor.execute('SELECT * FROM users WHERE name = ?', [user])\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="safe_list.py")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive on parameterized list: {criticals}"

    def test_safe_python_pep249_dictionary_parameters(self, taint_walker):
        """Python: cursor.execute('SELECT * FROM users WHERE name = %(name)s', {'name': user})"""
        code = (
            "def get_user(request):\n"
            "    user = request.args.get('user')\n"
            "    cursor.execute('SELECT * FROM users WHERE name = %(name)s', {'name': user})\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="safe_pep249_dict.py")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive on PEP 249 dictionary parameters: {criticals}"

    def test_safe_python_multiline_sink_call(self, taint_walker):
        """Python: Multi-line cursor.execute with parameters on separate lines."""
        code = (
            "def search(request):\n"
            "    user = request.args.get('user')\n"
            "    age = request.args.get('age')\n"
            "    cursor.execute(\n"
            "        'SELECT * FROM users WHERE name = %s AND age = %s',\n"
            "        (user, age)\n"
            "    )\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="safe_multiline.py")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive on multi-line parameterized call: {criticals}"

    def test_safe_python_explicit_int_cast(self, taint_walker):
        """Python: user_id = int(request.args.get('id')); cursor.execute(f'... {user_id}')"""
        code = (
            "def get_by_id(request):\n"
            "    user_id = int(request.args.get('id'))\n"
            "    cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="safe_int_cast.py")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive: int() cast flagged as CRITICAL: {criticals}"
        assert len(findings) >= 1
        assert findings[0].sanitized is True
        assert findings[0].severity == "LOW"

    def test_safe_python_explicit_float_cast(self, taint_walker):
        """Python: price = float(request.args.get('price')); cursor.execute(f'... {price}')"""
        code = (
            "def get_by_price(request):\n"
            "    price = float(request.args.get('price'))\n"
            "    cursor.execute(f\"SELECT * FROM products WHERE price > {price}\")\n"
        )
        findings = taint_walker.analyze_code(code, language="python", file_path="safe_float_cast.py")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive: float() cast flagged as CRITICAL: {criticals}"
        assert findings[0].sanitized is True

    def test_safe_javascript_parameterized_query(self, taint_walker):
        """JS: client.query('SELECT * FROM users WHERE id = $1', [userId])"""
        code = (
            "async function getUser(req, res) {\n"
            "    const userId = req.query.id;\n"
            "    const result = await client.query('SELECT * FROM users WHERE id = $1', [userId]);\n"
            "    res.json(result.rows);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="safe_js_param.js")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive on JS parameterized query: {criticals}"

    def test_safe_javascript_parseint_cast(self, taint_walker):
        """JS: const id = parseInt(req.query.id); db.query(`SELECT ... ${id}`)"""
        code = (
            "function getUser(req, res) {\n"
            "    const id = parseInt(req.query.id);\n"
            "    db.query(`SELECT * FROM users WHERE id = ${id}`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="safe_parseint.js")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive: parseInt() cast flagged as CRITICAL: {criticals}"
        assert findings[0].sanitized is True
        assert findings[0].severity == "LOW"

    def test_safe_javascript_number_cast(self, taint_walker):
        """JS: const id = Number(req.query.id); db.query(`SELECT ... ${id}`)"""
        code = (
            "function getUser(req, res) {\n"
            "    const id = Number(req.query.id);\n"
            "    db.query(`SELECT * FROM users WHERE id = ${id}`);\n"
            "}\n"
        )
        findings = taint_walker.analyze_code(code, language="javascript", file_path="safe_number.js")
        criticals = [f for f in findings if f.severity == "CRITICAL"]
        assert len(criticals) == 0, f"False positive: Number() cast flagged as CRITICAL: {criticals}"
        assert findings[0].sanitized is True
