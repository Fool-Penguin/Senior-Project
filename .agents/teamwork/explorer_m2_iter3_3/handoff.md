# Handoff Report: Investigation of Defect 5 (Dummy Parameter Container Bypass) & Adversarial Test Suite Regression Lock-in

**Agent:** `explorer_m2_iter3_3`  
**Parent / Recipient:** `cdd4c46b-fa83-40b4-992f-7161af706ca8` (orchestrator)  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_iter3_3`  
**Date:** 2026-11-01  
**Status:** COMPLETE (Read-Only Analysis & Design)  

---

## 1. Observation

### A. Code Inspection: Defect 5 in `codedee/codedee_server/app/taint/walker.py`
1. **Location:** `walker.py:169-173` in `is_sink_parameterized()`
   ```python
   # Line 169-173:
   # Check for secondary parameter argument: cursor.execute(query, (param1, param2)) or db.query(sql, [param1])
   if re.search(r",\s*(\(|\[|\{)", cleaned):
       return True

   return False
   ```
   - `re.search(r",\s*(\(|\[|\{)", cleaned)` performs an unconstrained search for a comma followed by `(`, `[`, or `{`.
   - It matches empty containers `()`, `( )`, `[]`, `[ ]`, `{}`, `{ }` because it does not require any element inside the container delimiters.
   - It also matches calls to empty container constructors if parenthesized: `tuple()`, `list()`, `dict()`.

2. **Location:** `walker.py:273-280` in `_find_taint_paths_in_dfg()`
   ```python
   # Lines 273-280:
   # Check for sanitization
   is_sanitized = self.is_sink_parameterized(snk_data, snk_line_text)
   for n_step in raw_path:
       n_data = dfg.nodes[n_step]
       if self.is_sanitizer_operation(n_data, {}):
           is_sanitized = True
           break
   ```
   - `is_sink_parameterized()` is invoked solely with `snk_line_text` (the text of the line containing the database sink call, e.g. `cursor.execute(sql, ())`).
   - If an unparameterized f-string, template literal, or string concatenation was executed on a preceding line (e.g. `sql = f"SELECT * FROM users WHERE name = '{user}'"`), `snk_line_text` only contains `cursor.execute(sql, ())`.
   - Because `snk_line_text` contains `, ()`, `is_sink_parameterized()` returns `True`.
   - `walker.py` then assigns:
     ```python
     severity="CRITICAL" if not is_sanitized else "LOW",
     sanitized=is_sanitized,
     symbolic_confidence=0.95 if not is_sanitized else 0.20,
     ```
   - Consequently, `is_sanitized` is erroneously set to `True`, and the severity is downgraded to `"LOW"`.

### B. Empirical Verification of Defect 5 Evasion
Running the empirical test from `test_adversarial_dfg_taint.py`:
```python
def evasion_empty_tuple():
    user = request.args.get("user")
    sql = f"SELECT * FROM users WHERE name = '{user}'"
    cursor.execute(sql, ())
```
Direct inspection of the DFG and Taint Walker output revealed:
- DFG Path:
  `request.args.get("user")` [taint_source] ->
  `user` [ASSIGN_DEF] ->
  `user` [VAR_READ] ->
  `<fstring>` [INTERPOLATION] ->
  `sql` [ASSIGN_DEF] ->
  `sql` [VAR_READ] ->
  `cursor.execute` [sql_sink]
- Finding reported: `cwe_id='CWE-89'`, `severity='LOW'`, `sanitized=True`.
- Furthermore, when testing non-empty dummy containers with an interpolated query string:
  ```python
  def evasion_dummy_param():
      user = request.args.get("user")
      sql = f"SELECT * FROM users WHERE name = '{user}'"
      cursor.execute(sql, ("dummy",))
  ```
  Result: `cwe_id='CWE-89'`, `severity='LOW'`, `sanitized=True`.
  Passing dummy parameters (`("dummy",)`) into an SQL sink where the query string itself is tainted by an f-string also completely bypasses detection.

### C. Review of Challenger 1's 23 Adversarial Tests in `test_adversarial_dfg_taint.py`
The test suite consists of 23 test functions across three distinct categories:
- **Section 1: Robust Passing Capabilities (13 tests)**
  1. `test_ast_nested_tuple_direct_formatting`: `% (((username,),),)` unrolling.
  2. `test_ast_multi_element_nested_tuple_formatting`: `% (prefix, (user,))`.
  3. `test_ast_dictionary_percent_formatting`: `% {"username": user, ...}`.
  4. `test_ast_set_collection_formatting`: `% {cat}`.
  5. `test_ast_deeply_nested_parenthesized_expression`: `+ ((((user)))) +`.
  6. `test_string_format_positional`: `str.format(user)`.
  7. `test_augmented_assignment_concat`: `sql += "..." + cat`.
  8. `test_javascript_template_literal_in_query_arg`: `db.query(\`...${req.query.term}\`)`.
  9. `test_typescript_template_literal_with_as_cast`: `rawUser as string`.
  10. `test_async_await_parenthesized_javascript`: `await (client.query(sql))`.
  11. `test_async_await_typescript_typed_query`: `await (client.query(query) as Promise<any>)`.
  12. `test_multihop_five_hops_assignment_chain`: 5-hop assignment chain `v1 -> v2 -> v3 -> v4 -> v5`.
  13. `test_multihop_branching_reassignment`: Conditional `if flag: token = ...`.

- **Section 2: Negative Controls / False Positive Prevention (5 tests)**
  14. `test_safe_parameterized_query_tuple`: `cursor.execute(sql, (user, role))` -> `sanitized=True`, 0 CRITICAL.
  15. `test_safe_parameterized_query_javascript_callback`: `db.query("... ?", [userId], cb)` -> `sanitized=True`, 0 CRITICAL.
  16. `test_safe_integer_cast_sanitization`: `int(raw_id)` -> `sanitized=True`, 0 CRITICAL.
  17. `test_safe_constant_fstring_no_user_input`: Constant f-string -> 0 CRITICAL findings.
  18. `test_safe_no_db_call_string_manipulation`: String formatting with no DB sink -> 0 findings.

- **Section 3: Empirical Defect Proofs (5 tests)**
  19. `test_demonstrate_defect_1_receiver_method_call_drops_taint`: `raw_user.replace(...)` drops receiver.
  20. `test_demonstrate_defect_2_python_await_syntax_fallthrough`: `await cursor.execute(...)` falls through.
  21. `test_demonstrate_defect_3_keyword_argument_taint_loss`: `"...".format(name=user)` drops kwargs.
  22. `test_demonstrate_defect_4_subscript_indexing_taint_loss`: `container[0]` drops subscript.
  23. `test_demonstrate_defect_5_dummy_parameter_container_bypass`: `cursor.execute(sql, ())` bypasses detection.

---

## 2. Logic Chain

1. **Step 1 (Root Cause of Empty Container Acceptance)**:
   - *Observation*: `walker.py:170` executes `re.search(r",\s*(\(|\[|\{)", cleaned)`.
   - *Inference*: In regular expressions, `\(` matches any opening parenthesis regardless of what follows. In `cursor.execute(sql, ())`, the string `", ()"` matches `, (`.
   - *Conclusion*: An empty tuple `()`, empty list `[]`, or empty dictionary `{}` satisfies the pattern despite carrying zero query parameters.

2. **Step 2 (Root Cause of Secondary Parameter Disconnect from Query String Taint)**:
   - *Observation*: `is_sink_parameterized` only evaluates `snk_line_text`. In multi-line query construction (`sql = f"...{user}..."` followed by `cursor.execute(sql, ...)`), `snk_line_text` does not contain `f"` or `+`.
   - *Inference*: The query string argument (`arg_0`) was already poisoned by untrusted data during prior string interpolation. Passing parameters (empty or non-empty) to `cursor.execute` does NOT neutralize the SQL injection flaw already embedded in `sql`.
   - *Conclusion*: To be safe, a sink call must NOT ONLY possess a non-empty parameter container, but the taint path reaching the sink must NOT contain any unparameterized string formatting (`flow_type == 'STRING_CONCAT'` or `'FORMAT_INTERPOLATION'`, or node kinds `INTERPOLATION`, `BINARY_OP`, or `.format`).

3. **Step 3 (Dual-Defense Architecture)**:
   - *Defense Layer 1 (Syntactic & Regex)*: Update `is_sink_parameterized()` to explicitly reject empty containers:
     `r",\s*(?:\(\s*\)|\[\s*\]|\{\s*\}|tuple\s*\(\s*\)|list\s*\(\s*\)|dict\s*\(\s*\))\s*(?:\)|,|$)"`
     and require non-empty container contents:
     `r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s])"`.
   - *Defense Layer 2 (Semantic DFG Path Inspection)*: In `_find_taint_paths_in_dfg()`, inspect all edges and nodes along `raw_path`. If any node or edge represents string interpolation, string concatenation, or `.format()`, then the query string itself is tainted. This overrides `is_sink_parameterized` and forces `is_sanitized = False` (unless an explicit type-cast sanitizer like `int()` was traversed).

4. **Step 4 (Test Suite Inversion & Regression Lock-in)**:
   - *Observation*: Challenger 1's Section 3 tests currently assert `len(vulns) == 0` or `f.sanitized is True` to demonstrate the defects without failing `pytest`.
   - *Inference*: Once the worker implements fixes for Defects 1 through 5, these 5 tests must be inverted to assert `len(vulns) >= 1` and `f.severity == "CRITICAL"`, `f.sanitized is False`.
   - *Conclusion*: By migrating and inverting all 5 defect tests and adding cross-language boundary tests into `codedee/codedee_server/tests/test_taint_walker.py`, the test suite guarantees 100% regression lock-in.

---

## 3. Caveats

1. **Read-Only Scope**: In accordance with the Teamwork Explorer role, no source code or test files in `codedee/` were modified.
2. **Type Cast Precedence**: Explicit type casts (e.g. `int()`, `float()`, `parseInt()`) correctly sanitize tainted data even if the sanitized integer is subsequently interpolated into an f-string (e.g. `clean = int(user); sql = f"SELECT * FROM items WHERE id = {clean}"`). This is verified by negative control test `test_safe_integer_cast_sanitization` and preserved in the dual-defense logic.

---

## 4. Conclusion & Actionable Specifications

### A. Proposed Remediation for `codedee/codedee_server/app/taint/walker.py`

#### Change 1: Enhance `is_sink_parameterized()` in `walker.py:165-174`
```python
<<<<
        # Strip JavaScript/TypeScript callback functions before checking for parameter container
        cleaned = re.sub(r",\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>.*", "", line_clean)
        cleaned = re.sub(r",\s*function\s*\(.*", "", cleaned)

        # Check for secondary parameter argument: cursor.execute(query, (param1, param2)) or db.query(sql, [param1])
        if re.search(r",\s*(\(|\[|\{)", cleaned):
            return True

        return False
====
        # Strip JavaScript/TypeScript callback functions before checking for parameter container
        cleaned = re.sub(r",\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>.*", "", line_clean)
        cleaned = re.sub(r",\s*function\s*\(.*", "", cleaned)

        # 1. Reject empty parameter containers: (), [], {}, tuple(), list(), dict()
        if re.search(
            r",\s*(?:\(\s*\)|\[\s*\]|\{\s*\}|tuple\s*\(\s*\)|list\s*\(\s*\)|dict\s*\(\s*\))\s*(?:\)|,|$)",
            cleaned,
        ):
            return False

        # 2. Require non-empty container contents:
        # e.g. cursor.execute(query, (param1, param2)), db.query(sql, [param1]), or cursor.execute(sql, {"user": user})
        if re.search(r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s])", cleaned):
            return True

        return False
>>>>
```

#### Change 2: Integrate DFG Path String Format Verification in `walker.py:273-280`
```python
<<<<
                    # Check for sanitization
                    is_sanitized = self.is_sink_parameterized(snk_data, snk_line_text)
                    for n_step in raw_path:
                        n_data = dfg.nodes[n_step]
                        if self.is_sanitizer_operation(n_data, {}):
                            is_sanitized = True
                            break
====
                    # Check for sanitization via parameter container at sink
                    is_sanitized = self.is_sink_parameterized(snk_data, snk_line_text)

                    # Verify if the taint path reaching the sink contains unparameterized string formatting
                    # (e.g. f-string interpolation, template literal, binary + / % concatenation, or .format())
                    has_unparameterized_string_format = False
                    for i in range(len(raw_path) - 1):
                        u_node = raw_path[i]
                        v_node = raw_path[i + 1]
                        u_data = dfg.nodes[u_node]
                        e_data = dfg.get_edge_data(u_node, v_node, default={})
                        flow_type = e_data.get("flow_type", "")

                        if flow_type in ("STRING_CONCAT", "FORMAT_INTERPOLATION"):
                            has_unparameterized_string_format = True
                            break
                        if u_data.get("node_kind") == "INTERPOLATION":
                            has_unparameterized_string_format = True
                            break
                        if u_data.get("node_kind") == "BINARY_OP" and any(
                            op in u_data.get("expression_text", "") for op in ("+", "%")
                        ):
                            has_unparameterized_string_format = True
                            break
                        if (
                            u_data.get("node_kind") == "CALL_ARG"
                            and u_data.get("var_name", "").endswith(".format")
                        ):
                            has_unparameterized_string_format = True
                            break

                    # If the query itself was constructed using unparameterized string formatting,
                    # passing secondary dummy parameters cannot sanitize it.
                    if has_unparameterized_string_format:
                        is_sanitized = False

                    # Check for explicit sanitizer operations along the path (e.g. int(), float(), parseInt())
                    # Explicit type casts override since they guarantee safety even if formatted into an f-string
                    for n_step in raw_path:
                        n_data = dfg.nodes[n_step]
                        if self.is_sanitizer_operation(n_data, {}):
                            is_sanitized = True
                            break
>>>>
```

---

### B. Test Suite Specifications for `codedee/codedee_server/tests/test_taint_walker.py`

When the worker agent implements the fixes for Defects 1–5, the following 10 lock-in tests (inverting Challenger 1's defect demonstrations and covering boundary variants) should be appended to `codedee_server/tests/test_taint_walker.py`:

```python
# ============================================================================
# Challenger 1 Defect Remediation Regression Tests (Lock-in Suite for Defects 1–5)
# ============================================================================

def test_lockin_defect_1_receiver_method_call_propagates_taint(walker):
    """
    Lock-in Test 9 (Defect 1 Remediation):
    Receiver method calls (e.g. raw_user.replace(...), user.strip(), raw.trim())
    must propagate taint to method return value and flag CRITICAL SQL injection.
    """
    code = """
from flask import request

def evasion_method_call():
    raw_user = request.args.get("user")
    fake_clean = raw_user.replace("'", "''")
    sql = f"SELECT * FROM users WHERE name = '{fake_clean}'"
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect1.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Receiver method invocation did not propagate taint into DFG!"
    assert any("replace" in step.get("symbol", "") or "raw_user" in step.get("symbol", "") for step in vulns[0].taint_path)


def test_lockin_defect_2_python_await_sink_detected(walker):
    """
    Lock-in Test 10 (Defect 2 Remediation):
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
    findings = walker.analyze_code(code, "python", "lockin_defect2.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Python 'await cursor.execute(...)' sink was not detected!"
    assert any("cursor.execute" in v.sink_node.get("expression", "") for v in vulns)


def test_lockin_defect_3_keyword_argument_taint_propagates(walker):
    """
    Lock-in Test 11 (Defect 3 Remediation):
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
    findings = walker.analyze_code(code, "python", "lockin_defect3.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Python keyword argument (name=user) taint was dropped!"


def test_lockin_defect_4_subscript_indexing_taint_propagates(walker):
    """
    Lock-in Test 12 (Defect 4 Remediation):
    Subscript access (e.g. container[0], data['user']) must propagate taint
    from collection definitions to use sites and flag CRITICAL SQL injection.
    """
    code = """
from flask import request

def handler():
    user = request.args.get("user")
    container = [user]
    sql = "SELECT * FROM items WHERE owner = '%s'" % container[0]
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "lockin_defect4.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Subscript indexing (container[0]) dropped taint!"


def test_lockin_defect_5_empty_tuple_bypass_rejected(walker):
    """
    Lock-in Test 13 (Defect 5 Remediation):
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
    Lock-in Test 14 (Defect 5 Boundary Remediation):
    Passing empty list [] or empty dict {} or empty constructor tuple() must be rejected.
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
    Lock-in Test 15 (Defect 5 Non-Empty Dummy Container Remediation):
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
    Lock-in Test 16 (Defect 5 JS Remediation):
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
    Lock-in Test 17 (Defect 5 TS Remediation):
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
    Lock-in Test 18 (Defect 5 Non-Regression Positive Control):
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
```

---

## 5. Verification Method

### Independent Verification Commands
```powershell
# 1. Run baseline server test suite (verifying zero baseline regressions)
pytest codedee/codedee_server/tests -v

# 2. Run the adversarial stress test suite
pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py -v

# 3. Once worker applies proposed patch, run target walker test suite
pytest codedee/codedee_server/tests/test_taint_walker.py -v
```

### Invalidation Conditions
This investigation report is invalidated if:
1. `cursor.execute(f"SELECT * FROM users WHERE name = '{user}'", ())` is marked `sanitized=True` or `severity="LOW"`.
2. `cursor.execute(f"SELECT * FROM users WHERE name = '{user}'", ("dummy",))` is marked `sanitized=True`.
3. `cursor.execute("SELECT * FROM users WHERE name = %s", (user,))` is marked `severity="CRITICAL"` (false positive regression).
