# Handoff Report: Investigation of Parameterization Precision in `walker.py`

**Agent ID:** `explorer_m2_iter4_3`  
**Role:** Read-Only Explorer / Investigator / Analyzer  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_iter4_3`  
**Target File Analyzed:** `codedee/codedee_server/app/taint/walker.py`  
**Related Files Examined:**  
- `codedee/codedee_server/app/graphs/dfg.py`  
- `codedee/codedee_server/tests/test_taint_walker.py`  
- `.agents/teamwork/challenger_m2_iter3_2/test_adversarial_cross_language.py`  
- `.agents/teamwork/reviewer_m2_iter3_2/handoff.md`  
- `.agents/teamwork/challenger_m2_iter3_2/handoff.md`  
**Patch Artifact:** `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_iter4_3\walker_parameterization.patch`  
**Verification Harness:** `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_iter4_3\verify_logic.py`  
**Parent Orchestrator:** `cdd4c46b-fa83-40b4-992f-7161af706ca8`  
**Date:** 2026-11-01  

---

## Executive Summary

This read-only investigation resolved the root causes of three critical parameterization precision defects in `walker.py`:
1. **Shortest-Path Parameterization Bypass (Challenger 2 Defect 1):** When untrusted input flows to both query interpolation and a parameter container (e.g. `cursor.execute(f"...{user}", (user,))`), `nx.shortest_path(dfg, src, snk)` traversed the 4-hop path through the parameter container rather than the 6-hop path through the string formatting, falsely marking live SQL injection as sanitized (`sanitized: True, severity: "LOW"`).
2. **Multi-Line Sink Call Truncation (Reviewer 2 Defect 1):** In `walker.py:286-293`, `snk_line_text` was assigned `snk_lines[snk_line_num - 1]`, inspecting only the first line of multi-line sink calls (e.g. `cursor.execute(`), stripping subsequent parameter arguments and falsely flagging legitimate parameterized queries as unsanitized `CRITICAL` SQL injections.
3. **Parameter Variables & PEP 249 Dictionary Syntax (Reviewer 2 Defect 2 & Challenger 1 Defect B):** In `walker.py:162` and `walker.py:178`, regex patterns strictly required inline collection literals (`(`, `[`, `{`), rejecting parameter variable identifiers (`params = (user,); cursor.execute(query, params)`) and PEP 249 dictionary parameter formatting (`%(name)s` with `{"name": user}`).

All three root causes have been isolated, an exact non-invasive patch designed, and 100% verified via an empirical test harness (`verify_logic.py`). Zero modifications were made to the source codebase during this investigation.

---

## 1. Observation

### A. Defect 1: Shortest-Path Parameterization Bypass (Challenger 2 Defect 1)
- **File & Line:** `codedee/codedee_server/app/taint/walker.py:276` and lines `295-327`
- **Observed Code:**
  ```python
  274: if nx.has_path(dfg, src, snk):
  275:     try:
  276:         raw_path = nx.shortest_path(dfg, src, snk)
  277:     except nx.NetworkXNoPath:
  278:         continue
  ...
  297:     has_unparameterized_string_format = False
  298:     for i in range(len(raw_path) - 1):
  ...
  305:         if flow_type in ("STRING_CONCAT", "FORMAT_INTERPOLATION"):
  306:             has_unparameterized_string_format = True
  307:             break
  ...
  325:     if has_unparameterized_string_format:
  326:         is_sanitized = False
  ```
- **Observed Behavior:**
  In `test_adversarial_cross_language.py`:
  ```python
  def test_demonstrate_defect_1a_python_concat_with_dummy_parameter(walker):
      code = """
      def search_account():
          user = request.args.get('user')
          sql = "SELECT * FROM users WHERE name = '" + user + "'"
          cursor.execute(sql, (user,))
      """
  ```
  Execution Command:
  `pytest .agents/teamwork/challenger_m2_iter3_2/test_adversarial_cross_language.py -v`
  Verbatim Failure:
  ```
  FAILED test_adversarial_cross_language.py::test_demonstrate_defect_1a_python_concat_with_dummy_parameter - AssertionError: Defect 1A Evasion Confirmed: cursor.execute(concat_sql, (user,)) bypassed taint walker! Findings were incorrectly marked sanitized: [SymbolicFinding(cwe_id='CWE-89', severity='LOW', sanitized=True, ...)]
  FAILED test_adversarial_cross_language.py::test_demonstrate_defect_1b_python_fstring_with_dummy_parameter
  FAILED test_adversarial_cross_language.py::test_demonstrate_defect_1c_ts_concat_with_dummy_parameter
  FAILED test_adversarial_cross_language.py::test_demonstrate_defect_1d_js_concat_with_dummy_parameter
  ```
  In DFG, `dfg.py:516-518` creates incoming edges to `snk` with `operation="arg_0"` for the query and `operation="arg_1"` for the parameter container:
  - Path 1 (Parameter container): `src -> user -> [id] -> snk` (4 hops)
  - Path 2 (Query construction): `src -> user -> binop (+) -> sql -> snk` (6 hops)
  `nx.shortest_path` selected Path 1. Because Path 1 bypassed `binop (+)`, `has_unparameterized_string_format` remained `False`, and `is_sink_parameterized()` matched `, (user,)`, falsely concluding the code was sanitized (`severity="LOW"`).

### B. Defect 2: Multi-Line Sink Call Line Truncation (Reviewer 2 Defect 1)
- **File & Line:** `codedee/codedee_server/app/taint/walker.py:286-293`
- **Observed Code:**
  ```python
  286: snk_line_text = (
  287:     snk_lines[snk_line_num - 1]
  288:     if 0 < snk_line_num <= len(snk_lines)
  289:     else snk_data.get("expression_text", "")
  290: )
  291: 
  292: # Check for sanitization via parameter container at sink
  293: is_sanitized = self.is_sink_parameterized(snk_data, snk_line_text)
  ```
- **Observed Behavior:**
  Given standard multi-line database invocations:
  ```python
  cursor.execute(
      "SELECT * FROM users WHERE name = %s",
      (user,)
  )
  ```
  `snk_line_num` points to line 1 (`cursor.execute(`). `snk_lines[snk_line_num - 1]` contains only `'    cursor.execute('`. The query string and parameter container are on lines 2 and 3, which were discarded. Consequently, `is_sink_parameterized(snk_data, '    cursor.execute(')` evaluated to `False`, falsely reporting a false-positive `CRITICAL` SQL injection on safe, standard-compliant code.

### C. Defect 3: Parameter Variables & PEP 249 Dictionary Syntax (Reviewer 2 Defect 2 & Challenger 1 Defect B)
- **File & Line:** `codedee/codedee_server/app/taint/walker.py:161-179`
- **Observed Code:**
  ```python
  161: # If line contains % formatting without secondary parameter container
  162: if "%" in line_clean and not re.search(r",\s*(\(|\[)", line_clean):
  163:     return False
  ...
  176: # 2. Require non-empty container contents:
  177: # e.g. cursor.execute(query, (param1, param2)), db.query(sql, [param1]), or cursor.execute(sql, {"user": user})
  178: if re.search(r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s])", cleaned):
  179:     return True
  ```
- **Observed Behavior:**
  1. Parameter variables: `params = (user,); cursor.execute(query, params)`.
     `cleaned` contains `, params`. Line 178 requires the second argument to start with `(`, `[`, or `{`. It rejects identifier names like `params`, returning `False` and creating false-positive `CRITICAL` findings.
  2. PEP 249 Dictionary Syntax: `cursor.execute("SELECT * FROM users WHERE name = %(name)s", {"name": user})`.
     Line 162 detects `"%"` (from `%(name)s`), but requires `(\(|\[)` after the comma. Because dictionaries begin with `{`, line 162 returns `False`, discarding legitimate dictionary parameterization.

---

## 2. Logic Chain

1. *Argument Distinction in SQL Sinks:*
   In all SQL execution sinks (`cursor.execute`, `cursor.executemany`, `db.query`, `client.query`, `pool.query`, `prisma.$queryRaw`), Argument 0 (`arg_0`) represents the SQL query statement itself. Argument 1 (`arg_1`) represents the parameters container.
2. *Shortest-Path Blindness:*
   When tainted user input is concatenated into `arg_0` AND passed to `arg_1`, `nx.shortest_path(dfg, src, snk)` blindly chooses the parameter container because `(user,)` requires fewer hops than `user -> + -> sql`.
3. *Sanitization Invalidation Rule:*
   If untrusted input flows into Argument 0 through string concatenation, f-string interpolation, template literals, or printf `%` formatting, passing parameters in Argument 1 can NEVER neutralize the injection. The injected SQL syntax is already baked into the command string before the database engine sees it.
4. *Deduction for Defect 1:*
   To eliminate the bypass, `walker.py` must query the predecessors of `snk` connected via `operation in ("arg_0", "kwarg_query", "kwarg_sql", "kwarg_operation", "kwarg_stmt", "kwarg_statement")`. If any path from `src` to `arg_0` exists that contains unparameterized string formatting, `raw_path` must be set to that path and `is_sanitized` forced to `False`. If no path reaches `arg_0` (as in legitimate parameterized queries where input only enters `arg_1`), `raw_path` remains the path to `arg_1`, preserving safe query classification (`sanitized: True, severity: "LOW"`).
5. *Deduction for Defect 2:*
   `dfg.py:489` preserves the entire CST node text across all lines in `snk_data["expression_text"]`. Overriding `snk_lines[snk_line_num - 1]` with `snk_call_text = snk_data.get("expression_text") or snk_line_text` restores the complete multi-line call for parameter inspection.
6. *Deduction for Defect 3:*
   Allowing dictionary braces `{` in line 162 and valid identifier characters `[a-zA-Z_][a-zA-Z0-9_]*` in lines 162 & 178 safely recognizes variable-bound parameters and PEP 249 dictionary mapping while keeping empty containers `()`, `[]`, `{}`, `None`, `null`, `undefined` strictly rejected.

---

## 3. Caveats

1. **Non-Parameter Identifiers in Argument 1:**
   In JavaScript, callback functions are sometimes passed as secondary arguments. The solution applies `flags=re.DOTALL` to callback stripping and explicitly checks `query_arg_preds` so that any query string concatenation overrides and forces `is_sanitized = False`.
2. **Explicit Sanitizer Precedence:**
   Explicit sanitizers (such as `int()`, `float()`, `parseInt()`) correctly override string formatting because converting input to an integer eliminates CWE-89 injection risk even if concatenated into an f-string. This behavior is fully preserved.
3. **Destructuring Assignment (Challenger 2 Defect 2):**
   Destructuring assignment issues (`object_pattern`, `array_pattern` in `dfg.py`) belong to `dfg.py` graph generation and are separate from `walker.py` parameterization precision.

---

## 4. Conclusion & Proposed Remediation

The root causes are completely localized to `walker.py`. The exact, verified solution comprises three targeted adjustments:

### Proposed Code Diff (Referenced to `walker_parameterization.patch`)

```python
# ==============================================================================
# Change 1: walker.py:162-178 (Support PEP 249 Dict Syntax & Parameter Variables)
# ==============================================================================
<<<<
        # If line contains % formatting without secondary parameter container
        if "%" in line_clean and not re.search(r",\s*(\(|\[)", line_clean):
            return False

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
====
        # If line contains % formatting without secondary parameter container
        if "%" in line_clean and not re.search(r",\s*(?:\(|\[|\{|[a-zA-Z_][a-zA-Z0-9_]*)", line_clean):
            return False

        # Strip JavaScript/TypeScript callback functions before checking for parameter container
        cleaned = re.sub(r",\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>.*", "", line_clean, flags=re.DOTALL)
        cleaned = re.sub(r",\s*function\s*\(.*", "", cleaned, flags=re.DOTALL)

        # 1. Reject empty parameter containers: (), [], {}, tuple(), list(), dict(), None, null, undefined
        if re.search(
            r",\s*(?:\(\s*\)|\[\s*\]|\{\s*\}|tuple\s*\(\s*\)|list\s*\(\s*\)|dict\s*\(\s*\)|None|null|undefined)\s*(?:\)|,|$)",
            cleaned,
        ):
            return False

        # 2. Require non-empty container contents or parameter variable identifiers:
        # e.g. cursor.execute(query, (param1, param2)), db.query(sql, [param1]), cursor.execute(sql, {"user": user}),
        # or cursor.execute(query, params) / db.query(sql, values)
        if re.search(r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s]|[a-zA-Z_][a-zA-Z0-9_]*)", cleaned):
            return True
>>>>
```

```python
# ==============================================================================
# Change 2: walker.py:282-327 (Query Arg 0 Precedence & Multi-Line Sink Extraction)
# ==============================================================================
<<<<
                if nx.has_path(dfg, src, snk):
                    try:
                        raw_path = nx.shortest_path(dfg, src, snk)
                    except nx.NetworkXNoPath:
                        continue

                    visited_paths.add(pair_key)

                    # Extract line content for sink
                    snk_line_num = snk_data.get("line_number", 1)
                    snk_code = file_sources.get(snk_file, "")
                    snk_lines = snk_code.splitlines()
                    snk_line_text = (
                        snk_lines[snk_line_num - 1]
                        if 0 < snk_line_num <= len(snk_lines)
                        else snk_data.get("expression_text", "")
                    )

                    # Check for sanitization via parameter container at sink
                    is_sanitized = self.is_sink_parameterized(snk_data, snk_line_text)
====
                if nx.has_path(dfg, src, snk):
                    visited_paths.add(pair_key)

                    # Extract line content and full call expression for sink
                    snk_line_num = snk_data.get("line_number", 1)
                    snk_code = file_sources.get(snk_file, "")
                    snk_lines = snk_code.splitlines()
                    snk_line_text = (
                        snk_lines[snk_line_num - 1]
                        if 0 < snk_line_num <= len(snk_lines)
                        else snk_data.get("expression_text", "")
                    )
                    snk_call_text = snk_data.get("expression_text") or snk_line_text

                    # 1. Specifically check the path reaching the query argument (arg 0)
                    # In SQL sink calls (execute, query, etc.), arg 0 is the SQL query statement.
                    # If untrusted input flows into arg 0 (via string concatenation, f-string,
                    # template literal, or % format), passing secondary parameters in arg 1
                    # cannot sanitize the injection.
                    query_arg_preds = [
                        pred for pred in dfg.predecessors(snk)
                        if dfg.get_edge_data(pred, snk, default={}).get("operation") in (
                            "arg_0", "kwarg_query", "kwarg_sql", "kwarg_operation", "kwarg_stmt", "kwarg_statement"
                        )
                    ]

                    raw_path = None
                    has_unparameterized_string_format = False

                    # Check reachable query argument predecessors
                    for q_pred in query_arg_preds:
                        if nx.has_path(dfg, src, q_pred):
                            cand_path = nx.shortest_path(dfg, src, q_pred) + [snk]
                            cand_has_formatting = False
                            for i in range(len(cand_path) - 1):
                                u_node = cand_path[i]
                                v_node = cand_path[i + 1]
                                u_data = dfg.nodes[u_node]
                                e_data = dfg.get_edge_data(u_node, v_node, default={})
                                flow_type = e_data.get("flow_type", "")

                                if flow_type in ("STRING_CONCAT", "FORMAT_INTERPOLATION"):
                                    cand_has_formatting = True
                                    break
                                if u_data.get("node_kind") == "INTERPOLATION":
                                    cand_has_formatting = True
                                    break
                                if u_data.get("node_kind") == "BINARY_OP" and any(
                                    op in u_data.get("expression_text", "") for op in ("+", "%")
                                ):
                                    cand_has_formatting = True
                                    break
                                if (
                                    u_data.get("node_kind") == "CALL_ARG"
                                    and u_data.get("var_name", "").endswith(".format")
                                ):
                                    cand_has_formatting = True
                                    break

                            if cand_has_formatting:
                                raw_path = cand_path
                                has_unparameterized_string_format = True
                                break
                            elif raw_path is None:
                                raw_path = cand_path

                    # If no path reaching arg 0 was found (e.g. genuine parameterized query
                    # where tainted input only enters through parameter container arg 1),
                    # use shortest path to snk
                    if raw_path is None:
                        try:
                            raw_path = nx.shortest_path(dfg, src, snk)
                        except nx.NetworkXNoPath:
                            continue

                    # Check for sanitization via parameter container at sink using full call text
                    is_sanitized = self.is_sink_parameterized(snk_data, snk_call_text)
>>>>
```

```python
# ==============================================================================
# Change 3: walker.py:388 (Full Multi-Line Expression in Finding Sink Node)
# ==============================================================================
<<<<
                        "expression": snk_line_text.strip(),
====
                        "expression": snk_call_text.strip(),
>>>>
```

---

## 5. Verification Method

### A. Independent Reproduction of Findings
Execute the comprehensive test harness in the agent's folder:
```powershell
python .agents/teamwork/explorer_m2_iter4_3/verify_logic.py
```
Expected output:
```
--- 1. Testing Shortest-Path Parameterization Bypass (Challenger 2 Defect 1) ---
Defect 1A (Python concat + (user,)) PASSED -> flagged CRITICAL
Defect 1B (Python f-string + (user,)) PASSED -> flagged CRITICAL
Defect 1C (TS concat + [id]) PASSED -> flagged CRITICAL
Defect 1D (JS concat + [tag]) PASSED -> flagged CRITICAL

--- 2. Testing Multi-Line Sink Call Truncation (Reviewer 2 Defect 1) ---
Multi-line sink call PASSED -> sanitized=True, severity=LOW

--- 3. Testing Parameter Variables (Reviewer 2 Defect 2) ---
Parameter variable PASSED -> sanitized=True, severity=LOW

--- 4. Testing PEP 249 Dictionary Syntax (Reviewer 2 Defect 2 & Challenger 1 Defect B) ---
PEP 249 inline dict PASSED -> sanitized=True, severity=LOW
PEP 249 var dict PASSED -> sanitized=True, severity=LOW

--- 5. Testing Existing Legitimate & Adversarial Protections ---
Empty tuple rejection PASSED -> CRITICAL
None parameter rejection PASSED -> CRITICAL
Safe int() cast PASSED -> LOW
Static query PASSED -> 0 findings

==============================================
ALL VERIFICATION SUITE CHECKS PASSED 100%!
==============================================
```

### B. Unit Test Specifications for `test_taint_walker.py`
The worker implementing this fix should add the following 8 tests to `codedee/codedee_server/tests/test_taint_walker.py`:
1. `test_defect_1_shortest_path_parameter_bypass_python_concat`
2. `test_defect_1_shortest_path_parameter_bypass_python_fstring`
3. `test_defect_1_shortest_path_parameter_bypass_ts_concat`
4. `test_defect_1_shortest_path_parameter_bypass_js_concat`
5. `test_multiline_sink_call_remains_sanitized`
6. `test_parameter_variable_remains_sanitized`
7. `test_pep249_dictionary_inline_remains_sanitized`
8. `test_pep249_dictionary_variable_remains_sanitized`

### C. Invalidation Conditions
This solution is invalidated if:
1. `cursor.execute("SELECT ... WHERE name = %s", (user,))` wrapped across multiple lines is flagged as `CRITICAL`.
2. `cursor.execute(sql, (user,))` with `sql = f"..."` is marked as `sanitized: True` (LOW).
3. Any of the 89 tests in `codedee/codedee_server/tests` or 74 tests in `codedee/tests_e2e` fail.
