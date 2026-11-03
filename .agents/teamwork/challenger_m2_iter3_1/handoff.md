# Handoff Report: Adversarial Stress-Test Verification — Milestone 2 Iteration 3

**Agent ID:** `challenger_m2_iter3_1`  
**Role:** Empirical Challenger (Critic / Specialist)  
**Caller / Orchestrator:** `cdd4c46b-fa83-40b4-992f-7161af706ca8`  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\challenger_m2_iter3_1`  
**Date:** 2026-11-01  
**Verdict:** **REJECT** (3 High-Impact Empirical Defects Discovered)

---

## 1. Observation

### A. Execution of Prior Test Suites
1. **Challenger 1 Adversarial Suite (`.agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py`):**
   - Command: `pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py -v`
   - Result: `23 passed in 0.55s`.
   - Confirmed: The 5 original evasion defects reported in Milestone 2 Iteration 2 pass under the specific test fixtures written by Challenger 1.
2. **Server Unit Test Suite (`codedee/codedee_server/tests`):**
   - Command: `pytest codedee/codedee_server/tests -v`
   - Result: `89 passed, 1 warning in 23.61s`.
   - Confirmed: No regressions against the existing unit and regression test suite.

### B. New Adversarial Stress Test Suite (`.agents/teamwork/challenger_m2_iter3_1/test_adversarial_m2_iter3.py`)
- Created 29 new adversarial test cases systematically covering deep method chaining, Python async layers, nested subscripts, and complex dummy parameter containers.
- Command: `pytest .agents/teamwork/challenger_m2_iter3_1/test_adversarial_m2_iter3.py -v`
- Result: `29 passed in 0.56s`.
- When running both suites together: `pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py .agents/teamwork/challenger_m2_iter3_1/test_adversarial_m2_iter3.py -v`:
  `52 passed in 0.71s`.

### C. Confirmed Empirical Defects Discovered

#### Defect A: Chained Sink Method Invocations AST Node ID Collision (CRITICAL False Negative Evasion)
- **Target File & Line:** `codedee/codedee_server/app/graphs/dfg.py:480`
- **Observed Code:**
  ```python
  call_id = f"{func_id}::call_{node.start_point.row + 1}_{node.start_point.column}"
  ```
- **Observed Behavior:**
  When an SQL sink is invoked via a chained method call, e.g.:
  - Python: `db.get_cursor().execute(query)` or `client.get_session().execute(query)` or `pool.acquire().query(sql)`
  - JavaScript: `pool.connect().query(query)`
  Tree-sitter produces an outer `call` (e.g. `db.get_cursor().execute(query)`) whose start point is `(row, col)`, and an inner receiver `call` (`db.get_cursor()`) that starts at the **exact same `(row, col)`**.
  Both calls generate the identical `call_id` key:
  - Outer call creates `call_id = ...::call_7_4` with `var_name="db.get_cursor().execute"`.
  - When evaluating `recv_node`, inner call creates `call_id = ...::call_7_4` with `var_name="db.get_cursor"`.
  NetworkX `add_node` overwrites `call_7_4` with the inner call's attributes, resetting `var_name` to `"db.get_cursor"`.
  Then `walker.py:is_sink_node` inspects `var_name`: `"db.get_cursor"` does not match `SQL_METHOD_SINKS` (`"execute"` / `"query"`).
  **Result:** Total findings: `0`. 100% false negative evasion across Python, JavaScript, and TypeScript whenever the database sink is reached via a chained call!
- **Empirical Proof Test:** `test_demonstrate_defect_a_chained_sink_call_id_collision_drops_sink` in `test_adversarial_m2_iter3.py:601`.

#### Defect B: Legitimate Parameterized Dictionary Query Rejection (HIGH False Positive Precision Flaw)
- **Target File & Line:** `codedee/codedee_server/app/taint/walker.py:162`
- **Observed Code:**
  ```python
  # If line contains % formatting without secondary parameter container
  if "%" in line_clean and not re.search(r",\s*(\(|\[)", line_clean):
      return False
  ```
- **Observed Behavior:**
  Standard PEP 249 / psycopg2 / pymysql dictionary-parameterized query:
  ```python
  cursor.execute("SELECT * FROM users WHERE name = %(name)s", {"name": user})
  ```
  The query string contains `%` (due to `%(name)s`). The secondary parameter container is a dictionary `{...}`.
  Line 162's regex `r",\s*(\(|\[)"` only matches `(` (tuple) and `[` (list). It **completely omits `{` (dictionary)**.
  Consequently, `not re.search(...)` evaluates to `True`, and line 163 returns `False` immediately, before line 178 (`r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s])"`) can inspect the dictionary parameter.
  **Result:** Legitimate parameterized dictionary queries are marked `sanitized=False` and reported as `CRITICAL` CWE-89 vulnerabilities!
- **Empirical Proof Test:** `test_demonstrate_defect_b_parameterized_dict_false_positive_rejection` in `test_adversarial_m2_iter3.py:623`.

#### Defect C: Multi-Level Subscript Statement Assignment Dropped & AST Node Collision (CRITICAL False Negative Evasion)
- **Target File & Lines:** `codedee/codedee_server/app/graphs/dfg.py:177–181` and `dfg.py:561`
- **Observed Code (`dfg.py:177-181`):**
  ```python
  # Subscript assignment: container[0] = user or data['key'] = user
  if left and left.type in ("subscript", "subscript_expression"):
      base_node = left.child_by_field_name("value") or left.child_by_field_name("object")
      if base_node and base_node.type == "identifier":
          var_name = self.cst_manager.get_node_text(base_node, source_bytes)
  ```
- **Observed Behavior:**
  When a multi-level subscript assignment is executed:
  ```python
  data = {"users": [None]}
  user = request.args.get("user")
  data["users"][0] = user
  cursor.execute(f"SELECT * FROM users WHERE name = '{data['users'][0]}'")
  ```
  The LHS `left` node is `data["users"][0]`. Its `base_node` is `data["users"]`, whose node type is `"subscript"`, NOT `"identifier"`.
  The condition `base_node.type == "identifier"` evaluates to `False`, and the statement assignment falls through without adding `CONTAINER_MUTATE` or `CONTAINER_ELEMENT` edges to the container.
  Furthermore, in `dfg.py:561`:
  `sub_id = f"{func_id}::subscript_{node.start_point.row + 1}_{node.start_point.column}"`
  For `data["users"][0]`, the outer subscript and inner subscript `data["users"]` share the exact same start position `(row, col)`. NetworkX overwrites the outer subscript node and produces a recursive self-loop `subscript_8_47 -> subscript_8_47`.
  **Result:** Taint stored via multi-level subscripts is completely lost, yielding `0` findings!
- **Empirical Proof Test:** `test_demonstrate_defect_c_nested_subscript_assignment_mutation_dropped` in `test_adversarial_m2_iter3.py:652`.

---

## 2. Logic Chain

1. **Defect A (Chained Sink AST ID Collision):**
   - *Observation:* Tree-sitter nested call expressions `f().g()` share the same `start_point` column because `f()` is the start of `f().g()`.
   - *Observation:* `dfg.py:480` computes `call_id = f"{func_id}::call_{node.start_point.row + 1}_{node.start_point.column}"` using only `start_point`.
   - *Logic:* When `_process_expression` evaluates `db.get_cursor().execute(query)`, it assigns ID `call_7_4` with `var_name="db.get_cursor().execute"`. Next, it evaluates the receiver `recv_node = db.get_cursor()`, which is also a call starting at `(7, 4)`. This creates another node with the identical ID `call_7_4`, overwriting `var_name` to `"db.get_cursor"`.
   - *Logic:* `walker.py:118-127` tests `method in self.SQL_METHOD_SINKS`. For `"db.get_cursor"`, method is `"get_cursor"`, which is not in `SQL_METHOD_SINKS`.
   - *Conclusion:* Chained method sinks are dropped from the DFG, causing false-negative evasion.
   - *Suggested Fix:* Incorporate `node.end_point.row + 1` and `node.end_point.column` into `call_id` (and all other expression IDs):
     `call_id = f"{func_id}::call_{node.start_point.row + 1}_{node.start_point.column}_{node.end_point.row + 1}_{node.end_point.column}"`.

2. **Defect B (Dictionary Parameterization False Positive):**
   - *Observation:* `walker.py:162` tests `if "%" in line_clean and not re.search(r",\s*(\(|\[)", line_clean): return False`.
   - *Observation:* PEP 249 dictionary parameterized queries contain `%` in the SQL placeholder (e.g. `%(name)s`) and pass a dict `{...}` as the secondary parameter.
   - *Logic:* A dictionary container begins with `{`, which is neither `(` nor `[`. Therefore `not re.search(r",\s*(\(|\[)", line_clean)` evaluates to `True`, and line 163 returns `False` immediately.
   - *Conclusion:* Legitimate dictionary parameterization is classified as unsanitized, producing false positive `CRITICAL` findings.
   - *Suggested Fix:* Include `\{` in the regex at line 162:
     `if "%" in line_clean and not re.search(r",\s*(\(|\[|\{)", line_clean): return False`.

3. **Defect C (Multi-Level Subscript Mutation Dropped):**
   - *Observation:* `dfg.py:179` inspects `base_node = left.child_by_field_name("value") or left.child_by_field_name("object")` and strictly requires `base_node.type == "identifier"`.
   - *Logic:* In nested subscripts `data["users"][0]`, `base_node` is a `"subscript"` or `"subscript_expression"`. To find the root variable name, the AST must unwind nested subscripts until reaching the terminal `identifier`.
   - *Conclusion:* Because unwinding is missing, any assignment to a nested index is dropped from DFG def-use tracking.
   - *Suggested Fix:* Unwind nested subscripts iteratively:
     ```python
     curr_base = base_node
     while curr_base and curr_base.type in ("subscript", "subscript_expression"):
         curr_base = curr_base.child_by_field_name("value") or curr_base.child_by_field_name("object")
     if curr_base and curr_base.type == "identifier":
         var_name = self.cst_manager.get_node_text(curr_base, source_bytes)
     ```
     And include `end_point` in `sub_id` at `dfg.py:561`:
     `sub_id = f"{func_id}::subscript_{node.start_point.row + 1}_{node.start_point.column}_{node.end_point.row + 1}_{node.end_point.column}"`.

---

## 3. Caveats

- Challenger 1's 23 test fixtures remain valid and passing. The remediations made by Worker M2 Iteration 3 successfully solved the original 5 test fixtures, but left the structural AST ID collision vulnerability and regex asymmetry in place.
- In accordance with Key Constraints, no implementation code (`dfg.py`, `walker.py`) was modified by this challenger. All findings are strictly backed by executable tests in `test_adversarial_m2_iter3.py`.

---

## 4. Conclusion

**VERDICT: REJECT.**

Milestone 2 Iteration 3 cannot be approved in its current state because:
1. **Defect A** allows 100% evasion for any real-world database access pattern that chains connection or transaction acquisition (e.g. `db.get_cursor().execute(...)`, `pool.acquire().query(...)`, `pool.connect().query(...)`).
2. **Defect B** introduces false positives on standard, secure Python dictionary parameterized queries (`cursor.execute("SELECT ... WHERE name = %(name)s", {"name": user})`).
3. **Defect C** drops taint propagation whenever untrusted data is assigned to nested collections (`data['users'][0] = user`).

A remediation worker must be dispatched to fix these three defects before Milestone 2 can be certified for Milestone 3 progression.

---

## 5. Verification Method

### A. Independent Verification Commands
```powershell
# 1. Run the new adversarial suite reproducing all passing capabilities and the 3 confirmed defects:
pytest .agents/teamwork/challenger_m2_iter3_1/test_adversarial_m2_iter3.py -v

# 2. Run Challenger 1's adversarial test suite:
pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py -v

# 3. Run both adversarial suites together (52 tests):
pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py .agents/teamwork/challenger_m2_iter3_1/test_adversarial_m2_iter3.py -v

# 4. Run the baseline server unit test suite:
pytest codedee/codedee_server/tests -v
```

### B. Invalidation Conditions
This verdict is invalidated only if:
1. `db.get_cursor().execute(f"SELECT * FROM items WHERE owner = '{user}'")` produces a `CRITICAL` finding with a valid taint path without modifying the test assertion.
2. `cursor.execute("SELECT * FROM users WHERE name = %(name)s", {"name": user})` is classified as `sanitized=True` with `LOW` severity.
3. `data["users"][0] = user; cursor.execute(f"SELECT * FROM users WHERE name = '{data['users'][0]}'")` detects the CWE-89 injection with `sanitized=False`.
