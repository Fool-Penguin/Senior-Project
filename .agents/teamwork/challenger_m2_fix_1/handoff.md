# Handoff Report: Adversarial Stress Testing — Milestone 2 DFG & Taint Flow

**Agent:** `challenger_m2_fix_1`  
**Parent / Recipient:** `cdd4c46b-fa83-40b4-992f-7161af706ca8` (orchestrator)  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\challenger_m2_fix_1`  
**Date:** 2026-11-01  
**Status:** COMPLETE  
**Verdict:** **REJECT** (Milestone 2 requires remediation of 5 critical/high taint tracking evasion defects)

---

## 1. Observation

### A. Baseline Test Execution
1. The baseline server test suite `pytest codedee/codedee_server/tests -v` was executed and completed with **75 passed in 24.74s**.
2. The full adversarial challenge suite `pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py -v` was executed and completed with **23 passed in 0.60s**, verifying 18 robust language capabilities and empirically demonstrating 5 evasion vulnerabilities.

### B. Empirical Defect Discoveries

#### Defect 1: Receiver Object Disconnection on Method Invocations (CRITICAL FALSE NEGATIVE)
- **Location:** `codedee/codedee_server/app/graphs/dfg.py:436-467` (`_process_expression` for `call` / `call_expression`)
- **Code Inspection:**
  ```python
  if node_type in ("call", "call_expression"):
      fn_node = node.child_by_field_name("function")
      fn_text = self.cst_manager.get_node_text(fn_node, source_bytes) if fn_node else "call"
      args_node = node.child_by_field_name("arguments")
      ...
      if args_node:
          for arg_child in args_node.children:
              ...
              arg_ids = self._process_expression(arg_child, ...)
              for aid in arg_ids:
                  self.graph.add_edge(aid, call_id, ...)
      return [call_id]
  ```
- **Observed Behavior:**
  When a method is called on a tainted variable in Python, JavaScript, or TypeScript (e.g. `raw_user.replace("'", "''")`, `user.strip()`, `raw.trim()`, `user.toLowerCase()`), `fn_node` is an `attribute` or `member_expression` whose base object is the tainted variable.
  Because `_process_expression` never recursively extracts sub-expressions from `fn_node`, the receiver variable is never read. The Def-Use chain is completely severed at any method call.
- **Empirical Test:** `test_demonstrate_defect_1_receiver_method_call_drops_taint`
  ```python
  def evasion_method_call():
      raw_user = request.args.get("user")
      fake_clean = raw_user.replace("'", "''")
      sql = f"SELECT * FROM users WHERE name = '{fake_clean}'"
      cursor.execute(sql)
  ```
  Result: **0 findings reported** (`len(vulns) == 0`). A blatant SQL injection completely evades detection.

#### Defect 2: Python `await` Syntax Node Fallthrough (CRITICAL FALSE NEGATIVE)
- **Location:** `codedee/codedee_server/app/graphs/dfg.py:534`
- **Code Inspection:**
  ```python
  if node_type in ("await_expression", "as_expression", "type_assertion", "non_null_expression", "unary_operator", "unary_expression"):
  ```
- **Observed Behavior:**
  In Tree-sitter Python, `await cursor.execute(query)` is parsed as an AST node with type `"await"`, NOT `"await_expression"` (which is JavaScript/TypeScript).
  Because `"await"` is missing from the syntactic wrapper check, Python `await cursor.execute(...)` falls through to the literal fallback at line 542 (`node_kind="EXPRESSION"`). The inner `call` node is never evaluated, meaning `cursor.execute` is NEVER registered as a `CALL_ARG` node. Consequently, `is_sink_node()` never encounters the sink.
- **Empirical Test:** `test_demonstrate_defect_2_python_await_syntax_fallthrough`
  ```python
  async def async_fetch():
      user = request.args.get("user")
      query = f"SELECT * FROM sessions WHERE user = '{user}'"
      await cursor.execute(query)
  ```
  Result: **0 findings reported** (`len(vulns) == 0`). 100% of Python asynchronous database execution sinks evade detection.

#### Defect 3: Python Keyword Arguments Omission in Calls (HIGH FALSE NEGATIVE)
- **Location:** `codedee/codedee_server/app/graphs/dfg.py:456-466`
- **Code Inspection:**
  In Tree-sitter Python, named arguments like `name=user` in `"...".format(name=user)` or `db_helper(query=sql)` are parsed with AST node type `"keyword_argument"`.
  In `_process_expression`, `"keyword_argument"` has no handler. It falls through to the literal fallback at line 542 without extracting its child expression (`value`), dropping the identifier `user`.
- **Empirical Test:** `test_demonstrate_defect_3_keyword_argument_taint_loss`
  ```python
  def handler():
      user = request.args.get("username")
      sql = "SELECT * FROM users WHERE name = '{name}'".format(name=user)
      cursor.execute(sql)
  ```
  Result: **0 findings reported** (`len(vulns) == 0`).

#### Defect 4: Subscript Indexing Expression Omission (HIGH FALSE NEGATIVE)
- **Location:** `codedee/codedee_server/app/graphs/dfg.py:541-556`
- **Code Inspection:**
  Neither Python `subscript` (`container[0]`, `data['key']`) nor JS/TS `subscript_expression` is handled in `_process_expression`. Any element accessed by index or dictionary key falls through to literal fallback, severing the DFG connection to the container's definition.
- **Empirical Test:** `test_demonstrate_defect_4_subscript_indexing_taint_loss`
  ```python
  def handler():
      user = request.args.get("user")
      container = [user]
      sql = "SELECT * FROM items WHERE owner = '%s'" % container[0]
      cursor.execute(sql)
  ```
  Result: **0 findings reported** (`len(vulns) == 0`).

#### Defect 5: Parameterization Bypass via Dummy Secondary Parameters (CRITICAL FALSE NEGATIVE)
- **Location:** `codedee/codedee_server/app/taint/walker.py:143-174` (`is_sink_parameterized`)
- **Code Inspection:**
  ```python
  # walker.py:170
  if re.search(r",\s*(\(|\[|\{)", cleaned):
      return True
  ```
  `is_sink_parameterized` only inspects the line of the sink invocation (e.g. `cursor.execute(sql, ())`).
  If `sql` was constructed using an unparameterized f-string or string concatenation on a prior line (`sql = f"SELECT * FROM users WHERE name = '{user}'"`), passing an empty tuple `()`, empty list `[]`, or empty dictionary `{}` to `cursor.execute(sql, ())` matches `, (` and causes `is_sink_parameterized` to return `True`.
  The finding is erroneously classified as `sanitized=True` and demoted to `LOW` severity.
- **Empirical Test:** `test_demonstrate_defect_5_dummy_parameter_container_bypass`
  ```python
  def evasion_empty_tuple():
      user = request.args.get("user")
      sql = f"SELECT * FROM users WHERE name = '{user}'"
      cursor.execute(sql, ())
  ```
  Result: **Falsely marked `sanitized=True` with `severity="LOW"`**. Trivial evasion of CWE-89 detection.

---

## 2. Logic Chain

1. **Step 1 (Method Call Taint Severance)**:
   - *Observation*: In `dfg.py:436`, `_process_expression` inspects `node.child_by_field_name("function")` only to get its string representation `fn_text`, without calling `self._process_expression` on it.
   - *Inference*: In expressions like `obj.method()`, `obj` is embedded in the `function` AST node. Omitting recursive processing of `fn_node` prevents the creation of a `VAR_READ` node for `obj`.
   - *Conclusion*: Any method invocation on tainted data across Python, JS, and TS drops taint propagation, causing false negatives.

2. **Step 2 (Python Await Wrapper Blind Spot)**:
   - *Observation*: Tree-sitter Python creates node type `"await"` for `await cursor.execute(query)`, while `dfg.py:534` only checks `"await_expression"`.
   - *Inference*: The node type mismatch causes Python `await` expressions to fall through to literal fallback, hiding the inner `call` node from the DFG.
   - *Conclusion*: Python asynchronous database calls are completely invisible to the taint walker.

3. **Step 3 (Keyword Arguments & Subscripts Omission)**:
   - *Observation*: `keyword_argument` and `subscript` AST node types are absent from `_process_expression` branching in `dfg.py`.
   - *Inference*: Tainted variables passed as keyword arguments (e.g. `.format(key=val)`) or stored in collections and indexed (`arr[0]`) fall through without edge creation.
   - *Conclusion*: Untrusted data passed via keyword arguments or extracted via subscript access evades taint tracking.

4. **Step 4 (Line-Local Parameterization Heuristic Flaw)**:
   - *Observation*: `is_sink_parameterized` in `walker.py:170` checks `re.search(r",\s*(\(|\[|\{)", cleaned)` purely on the sink invocation line text.
   - *Inference*: It assumes that any trailing comma and bracket indicates safe parameterization, without verifying whether the primary query string argument was already constructed via interpolation/concatenation.
   - *Conclusion*: Unparameterized queries formed on prior lines are trivially marked `sanitized=True` if dummy empty containers `()` or `{}` are supplied.

---

## 3. Caveats

1. **Production Code Untouched**: In compliance with the EMPIRICAL CHALLENGER mandate, zero changes were made to `codedee/codedee_server/app/graphs/dfg.py` or `codedee/codedee_server/app/taint/walker.py`.
2. **Existing Test Suite Baseline**: All 75 unit tests in `codedee/codedee_server/tests` continue to pass. The 5 defects identified represent adversarial gaps not exercised by the current unit tests.

---

## 4. Conclusion & Verdict

**VERDICT: REJECT**

While Milestone 2 successfully handles direct tuple unrolling, dictionary formatting, and JS template literals, the engine suffers from **5 critical/high evasion vulnerabilities**:
1. **Defect 1 (CRITICAL)**: Method call receiver omission in DFG (`user.strip()`, `raw.trim()`, `fake_clean = raw.replace(...)`).
2. **Defect 2 (CRITICAL)**: Python `await` AST node type omission in syntactic wrapper matching (`await cursor.execute(...)`).
3. **Defect 3 (HIGH)**: Python `keyword_argument` AST node omission (`"...".format(name=user)`).
4. **Defect 4 (HIGH)**: Subscript/indexing expression omission (`container[0]`, `data['user']`).
5. **Defect 5 (CRITICAL)**: Dummy parameter container bypass in `is_sink_parameterized` (`cursor.execute(f"...", ())`).

Remediation by a worker agent is required to close these evasion vectors before Milestone 2 can be approved.

---

## 5. Verification Method

### Reproduction Commands
```powershell
# Run the adversarial challenge test suite demonstrating robust features and defect proofs
pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py -v
# Output: 23 passed in ~0.60s

# Run existing server unit tests to confirm baseline
pytest codedee/codedee_server/tests -v
# Output: 75 passed in ~24s
```

### Remediation Guidance for Worker
1. **Fix Defect 1 in `dfg.py:436`**: In `call` / `call_expression`, extract receiver nodes from `fn_node` (e.g. if `fn_node.type in ("attribute", "member_expression")`, process `fn_node.child_by_field_name("object")` or recursively call `_process_expression(fn_node)`).
2. **Fix Defect 2 in `dfg.py:534`**: Add `"await"` to the tuple: `if node_type in ("await", "await_expression", ...):`.
3. **Fix Defect 3 in `dfg.py:456`**: Handle `keyword_argument` by extracting `child.child_by_field_name("value")`.
4. **Fix Defect 4 in `dfg.py:534`**: Handle `subscript` and `subscript_expression` by extracting and connecting the base object `node.child_by_field_name("value")` or `node.children[0]`.
5. **Fix Defect 5 in `walker.py:170`**: In `is_sink_parameterized`, check whether the query argument node has incoming `STRING_CONCAT` or `INTERPOLATION` edges from the DFG before declaring it parameterized, or reject empty containers `re.search(r",\s*(\(\s*\)|\[\s*\]|\{\s*\})", cleaned)`.

### Invalidation Conditions
This rejection is invalidated if:
1. `raw_user.replace("'", "''")` or `user.strip()` with an f-string produces a `CRITICAL` unsanitized finding.
2. `await cursor.execute(query)` where `query` is tainted produces a `CRITICAL` finding.
3. `cursor.execute(f"...", ())` is flagged as `CRITICAL` unsanitized rather than `sanitized=True` / `LOW`.
