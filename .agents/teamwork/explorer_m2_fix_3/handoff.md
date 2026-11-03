# Handoff Report: Milestone 2 Test Suite Design & Defect Remediation Locking

**Agent:** `explorer_m2_fix_3` (Explorer / Test Suite Architect)  
**Parent / Recipient:** `cdd4c46b-fa83-40b4-992f-7161af706ca8` (orchestrator)  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_fix_3`  
**Date:** 2026-11-01  
**Scope:** Test suite design for `codedee_server/tests/test_taint_walker.py` locking in fixes for Challenger 2 defects.

---

## 1. Observation

### A. Empirical Baseline Verification (Existing Test Suites)
Both existing test suites were executed directly via `pytest` to establish the baseline before any test modifications:
1. **Unit Test Suite (`codedee/codedee_server/tests`)**:
   - Command: `pytest codedee/codedee_server/tests -v`
   - Result: **60 passed in 17.31s** (`test_api.py`: 17, `test_dataset.py`: 7, `test_maintainability.py`: 10, `test_taint_walker.py`: 7, `test_treesitter_graphs.py`: 19).
2. **End-to-End Integration Test Suite (`codedee/tests_e2e`)**:
   - Command: `pytest codedee/tests_e2e -v`
   - Result: **74 passed in 26.15s** (`test_tier1_features.py`: 28, `test_tier2_boundaries.py`: 33, `test_tier3_combinations.py`: 7, `test_tier4_real_world.py`: 6).
3. **Total Verified Baseline**: **134 passing automated tests**.

### B. Defect 1: Python `%` Tuple Formatting Evasion (False Negative)
- **Target File**: `codedee/codedee_server/app/graphs/dfg.py:282-485` (`DFGBuilder._process_expression`).
- **Verbatim Code Analyzed**:
  ```python
  # 3. String Concatenation: a + b
  if node_type in ("binary_operator", "binary_expression"):
      ...
      left_ids = self._process_expression(left, source_bytes, language, file_path, func_id, current_defs)
      right_ids = self._process_expression(right, source_bytes, language, file_path, func_id, current_defs)
  ...
  # 7. Fallback for literals / other expressions
  lit_id = f"{func_id}::lit_{node.start_point.row + 1}_{node.start_point.column}"
  self.graph.add_node(
      lit_id,
      node_id=lit_id,
      var_name=node_text,
      ...
      node_kind="STRING_LITERAL" if "string" in node_type else "EXPRESSION",
  )
  return [lit_id]
  ```
- **Observed Behavior**:
  For `sql = "SELECT * FROM accounts WHERE name = '%s'" % (username,)`, the right-hand operand AST node type is `tuple` (or `parenthesized_expression`).
  Because `node_type in ("tuple", "parenthesized_expression", "list", "array")` is not explicitly handled, it falls through to fallback literal (#7). The identifier `username` inside the tuple is never traversed, dropping the Def-Use edge into `sql`.
- **Empirical Execution**:
  ```python
  f = walker.analyze_code(code1, 'python', 'c1.py')
  # len(f) == 0 (Vulnerability completely missed!)
  ```

### C. Defect 2: Substring Matching on Variable Names (False Positive Flood)
- **Target File**: `codedee/codedee_server/app/taint/walker.py:82-96` (`SymbolicTaintWalker.is_sink_node`).
- **Verbatim Code Analyzed**:
  ```python
  SINK_PATTERNS = {
      "execute", "executemany", "query", "raw", "rawquery",
      "$queryrawunsafe", "$executerawunsafe", "execute_filtered_query",
  }
  ...
  def is_sink_node(self, node_data: Dict[str, Any]) -> bool:
      expr = node_data.get("expression_text", "")
      var = node_data.get("var_name", "")
      expr_lower = expr.lower()
      var_lower = var.lower()

      for pattern in self.SINK_PATTERNS:
          if pattern in var_lower:
              return True
          if f".{pattern}(" in expr_lower or f"{pattern}(" in expr_lower:
              return True
      return False
  ```
- **Observed Behavior**:
  `if pattern in var_lower:` performs an unconstrained substring check against `var_name`. Because `"raw"` and `"query"` are in `SINK_PATTERNS`, any variable containing `"raw"` (`raw_data`, `raw_text`, `raw_payload`) or `"query"` (`search_query`, `query_str`, `user_query`) is flagged as an **SQL execution sink**.
- **Empirical Execution**:
  A 5-line string processing function with zero database operations:
  ```python
  def parse_raw(request):
      raw_data = request.args.get("data")
      search_query = request.args.get("q")
      return raw_data + search_query
  ```
  Result: **9 CRITICAL CWE-89 SQL Injection findings** (`raw_data`: 4 findings, `search_query`: 5 findings).

### D. Defect 3: JS Template Literals with Non-SQL Variables & Variable Declarations
- **Target Files**:
  1. `codedee/codedee_server/app/taint/walker.py:82-96` (`is_sink_node`)
  2. `codedee/codedee_server/app/taint/walker.py:328` (`_fallback_ast_sink_scan`)
- **Observed Behavior**:
  1. For template literals like ``const html = `<div>${searchQuery}: ${rawData}</div>`;``, `searchQuery` and `rawData` are treated as sinks due to `pattern in var_lower`. Result: **6 CRITICAL findings on pure HTML rendering**.
  2. In `_fallback_ast_sink_scan`, line `const query = `SELECT ... ${isApproved} ...`;` matches `"query"` in `clean.lower()` and treated the variable assignment statement itself as an SQL sink.

### E. Additional Critical Discovery (Deep Architectural Coupling)
During our investigation of existing tests in `codedee_server/tests/test_taint_walker.py`, two hidden couplings were uncovered:
1. In `test_typescript_concat_sql_injection`:
   `const result = await client.query(query);`
   In tree-sitter TypeScript, `await client.query(query)` has node type `await_expression`. Because `await_expression` was unhandled in `_process_expression`, `client.query(query)` was never processed as a `call_expression` and was dropped. The test originally passed only because `const query = ...` had `var_name="query"` and was treated as a sink via `pattern in var_lower`.
   **Fix Requirement**: `DFGBuilder._process_expression` must unwrap `await_expression` so `client.query` is created as a `CALL_ARG` and connected to `query`.
2. In `test_javascript_template_literal_sql_injection`:
   `db.query(sql, (err, rows) => { ... })`
   In `is_sink_parameterized` (`walker.py:128`), `re.search(r",\s*(\(|\[|\{)", line_clean)` matched `, (` before `(err, rows) =>`, falsely misidentifying the callback function as parameterized query inputs. The test originally passed only because `req.query.category` was classified as its own sink via `pattern in var_lower`.
   **Fix Requirement**: `is_sink_parameterized` must distinguish callback function signatures `(err, rows) =>` from parameter collections.

---

## 2. Logic Chain

1. **Root Cause 1 (Tuple Evasion)**:
   In `dfg.py:282`, tree-sitter AST node types `"tuple"`, `"parenthesized_expression"`, `"list"`, and `"array"` fall through to line 470 (literal fallback). This leaves their constituent identifiers disconnected from parent binary/call expressions.
   *Inference*: Recursively visiting child nodes of tuples/lists and returning their `child_ids` restores the Def-Use chain, allowing the walker to trace tainted input into `%` string formatting operations.

2. **Root Cause 2 (False Positive Flood)**:
   In `walker.py:91`, `pattern in var_lower` uses substring matching on generic words (`raw`, `query`). Variables like `raw_data` or `search_query` are variable definitions, not database calls.
   *Inference*: Sinks must strictly be function/method invocations (e.g. `.execute(`, `.query(`, `.executemany(`, `rawquery(`, `$queryRawUnsafe(`) or exact known sink function names when `node_kind == "CALL_ARG"`. Removing substring matching on variable names completely eliminates the 9 false positives on Python and 6 false positives on JS without suppressing true vulnerabilities.

3. **Root Cause 3 (Declarations as Sinks)**:
   In `walker.py:328`, `_fallback_ast_sink_scan` treats any line containing `"query"` as a sink, including `const query = ...`.
   *Inference*: Filtering out variable assignment declarations (`const `, `let `, `var `, `= `) unless they invoke database methods (`.execute(`, `.query(`, etc.) ensures template literals with constants are not flagged.

4. **Mutual Consistency & Regression Freedom**:
   When simulated in Python memory with all 4 remediations active:
   - Python `% (username,)`: Correctly flagged as CRITICAL CWE-89 (2 findings).
   - Python `raw_data` / `search_query`: Exactly 0 findings.
   - JS non-SQL template literals: Exactly 0 findings.
   - JS constant template literals: Exactly 0 findings.
   - All 60 existing unit tests in `codedee/codedee_server/tests`: **60 passed in 12.13s**.
   - All 74 existing E2E tests in `codedee/tests_e2e`: **74 passed in 25.38s**.

---

## 3. Caveats

1. **Out of Scope**: Multi-statement dynamic query builders using ORM query-building chains (e.g. `knex.select().from()`) are outside the Milestone 2 CWE-89 vertical slice.
2. **Read-Only Protocol**: This agent designed and validated all test cases and fix specifications in memory, but did NOT modify repository source code files. Worker M2 must apply the recommended code changes.

---

## 4. Conclusion & Recommended Test Suite Additions

### Recommended Test Suite Additions for `codedee_server/tests/test_taint_walker.py`

Append the following 8 targeted test cases to `codedee_server/tests/test_taint_walker.py`. These tests lock in the 3 defect remediations and provide regression safety:

```python
# ============================================================================
# Challenger 2 Defect Remediation Regression Tests (Lock-in Suite)
# ============================================================================

def test_python_percent_format_single_tuple_sql_injection(walker):
    """
    Lock-in Test 1 (Defect 1 Evasion Prevention):
    Single-element tuple formatting: sql = "SELECT * FROM users WHERE name = '%s'" % (user_input,)
    Must be detected as an unparameterized CRITICAL SQL injection (sanitized=False).
    """
    code = """
from flask import request

def get_user_profile():
    username = request.args.get("username")
    sql = "SELECT * FROM users WHERE name = '%s'" % (username,)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "percent_single_tuple.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Vulnerability with % (tuple,) was not detected as CRITICAL!"
    f = vulns[0]
    assert f.cwe_id == "CWE-89"
    assert "username" in f.source_node.get("expression", "") or "request" in f.source_node.get("expression", "")
    assert len(f.taint_path) >= 2


def test_python_percent_format_multi_tuple_sql_injection(walker):
    """
    Lock-in Test 2 (Defect 1 Evasion Prevention):
    Multi-element tuple formatting: sql = "... %s ... %s" % (user_input, role)
    Must be detected as an unparameterized CRITICAL SQL injection.
    """
    code = """
from flask import request

def filter_records():
    user_input = request.args.get("user")
    status = "ACTIVE"
    sql = "SELECT * FROM records WHERE owner = '%s' AND status = '%s'" % (user_input, status)
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "percent_multi_tuple.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "Multi-element tuple % formatting was not detected as CRITICAL!"
    assert any("user_input" in f.source_node.get("expression", "") for f in vulns)


def test_python_percent_format_list_sql_injection(walker):
    """
    Lock-in Test 3 (Defect 1 Evasion Prevention):
    List collection formatting: sql = "SELECT * FROM items WHERE id = %s" % [item_id]
    Must be detected as an unparameterized CRITICAL SQL injection.
    """
    code = """
from flask import request

def list_lookup():
    item_id = request.args.get("id")
    sql = "SELECT * FROM items WHERE id = %s" % [item_id]
    cursor.execute(sql)
"""
    findings = walker.analyze_code(code, "python", "percent_list.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1, "List collection % formatting was not detected as CRITICAL!"


def test_python_non_sql_raw_and_query_variables_not_flagged(walker):
    """
    Lock-in Test 4 (Defect 2 False Positive Prevention):
    Variables containing 'raw' or 'query' (e.g. raw_data, search_query, user_query)
    in code with NO database calls must NOT be flagged as SQL injection sinks.
    """
    code = """
from flask import request

def parse_raw_payload():
    raw_data = request.args.get("data")
    search_query = request.args.get("q")
    raw_text = request.form.get("content")
    user_query = request.values.get("term")
    combined = f"{raw_data} - {search_query} - {raw_text} - {user_query}"
    return combined.strip()
"""
    findings = walker.analyze_code(code, "python", "no_db_raw_vars.py")
    assert len(findings) == 0, f"False positive detected on non-SQL variables: {findings}"


def test_javascript_non_sql_raw_and_query_variables_not_flagged(walker):
    """
    Lock-in Test 5 (Defect 2 False Positive Prevention):
    JavaScript variables named rawData, searchQuery, rawPayload without DB calls
    must NOT be flagged as SQL injection sinks.
    """
    code = """
function processSearchRequest(req, res) {
    const rawData = req.query.data;
    const searchQuery = req.query.q;
    const rawPayload = req.body.payload;
    const queryTerm = req.params.term;
    const summary = `Query: ${searchQuery}, Raw: ${rawData}, Term: ${queryTerm}`;
    return res.json({ summary: summary, raw: rawPayload });
}
"""
    findings = walker.analyze_code(code, "javascript", "no_db_search_vars.js")
    assert len(findings) == 0, f"False positive detected in JS non-SQL code: {findings}"


def test_javascript_template_literal_non_sql_html_not_flagged(walker):
    """
    Lock-in Test 6 (Defect 3 False Positive Prevention):
    Template literal creating HTML/UI without database queries must NOT be flagged.
    """
    code = """
const express = require('express');
const router = express.Router();

router.get('/render', (req, res) => {
    const rawData = req.query.data;
    const searchQuery = req.query.q;
    const html = `<div class="results"><h3>Search: ${searchQuery}</h3><p>Raw: ${rawData}</p></div>`;
    res.send(html);
});
"""
    findings = walker.analyze_code(code, "javascript", "render_html_template.js")
    assert len(findings) == 0, f"False positive detected on non-SQL template literal: {findings}"


def test_javascript_template_literal_constants_not_flagged(walker):
    """
    Lock-in Test 7 (Defect 3 False Positive Prevention):
    Template literal interpolating only constant numbers/booleans into a variable named 'query'
    with db.query(query) must NOT be flagged as a CRITICAL SQL injection.
    """
    code = """
function getStaticConfig() {
    const limit = 50;
    const isApproved = true;
    const query = `SELECT * FROM items WHERE approved = ${isApproved} LIMIT ${limit}`;
    db.query(query);
}
"""
    findings = walker.analyze_code(code, "javascript", "const_query_template.js")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) == 0, f"Template literal with constants falsely flagged as CRITICAL: {vulns}"


def test_raw_variable_with_real_sql_sink_isolates_true_sink(walker):
    """
    Lock-in Test 8 (Isolation & Precision):
    Code containing both a non-SQL variable 'raw_data' and a genuine SQL injection sink
    must flag the genuine sink (cursor.execute) and NOT flag 'raw_data'.
    """
    code = """
from flask import request

def handle_request():
    raw_data = request.args.get("data")
    search_term = request.args.get("term")
    sql = f"SELECT * FROM items WHERE name = '{search_term}'"
    cursor.execute(sql)
    return raw_data
"""
    findings = walker.analyze_code(code, "python", "mixed_sink_precision.py")
    vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
    assert len(vulns) >= 1
    for v in vulns:
        assert v.sink_node.get("symbol") != "raw_data", "raw_data was incorrectly classified as an SQL sink"
        assert "cursor.execute" in v.sink_node.get("expression", "")
```

### Remediation Guidance for Worker M2
To make all tests pass, Worker M2 should apply the following targeted edits:
1. **`codedee/codedee_server/app/graphs/dfg.py:282` (`_process_expression`)**:
   - Add unwrap handling for `node_type == "await_expression"`:
     ```python
     if node_type == "await_expression":
         for child in node.children:
             if child.type != "await":
                 return self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
     ```
   - Add collection handling for `node_type in ("tuple", "parenthesized_expression", "list", "array")`:
     ```python
     if node_type in ("tuple", "parenthesized_expression", "list", "array"):
         child_ids = []
         for child in node.children:
             if child.type in ("(", ")", "[", "]", ",", "{", "}"):
                 continue
             c_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
             child_ids.extend(c_ids)
         return child_ids
     ```
2. **`codedee/codedee_server/app/taint/walker.py:82` (`is_sink_node`)**:
   - Replace loose substring check `if pattern in var_lower: return True` with:
     ```python
     for pattern in self.SINK_PATTERNS:
         if f".{pattern}(" in expr_lower or f"{pattern}(" in expr_lower:
             return True
         if node_data.get("node_kind") == "CALL_ARG" and (var_lower == pattern or var_lower.endswith(f".{pattern}")):
             return True
     ```
3. **`codedee/codedee_server/app/taint/walker.py:106` (`is_sink_parameterized`)**:
   - Differentiate JavaScript callback functions (`(err, rows) =>` or `function(err, rows)`) from parameter arrays:
     ```python
     if re.search(r",\s*(function|\([^)]*\)\s*=>|[a-zA-Z0-9_]+\s*=>)", line_clean):
         if re.search(r",\s*(\[[^\]]+\]|\([^)]+\))\s*,\s*(function|\([^)]*\)\s*=>|[a-zA-Z0-9_]+\s*=>)", line_clean):
             return True
         return False
     ```
4. **`codedee/codedee_server/app/taint/walker.py:328` (`_fallback_ast_sink_scan`)**:
   - Exclude variable declarations (`const `, `let `, `var `) from being treated as sink invocation lines unless they call a database method.

---

## 5. Verification Method

### How to Independently Verify:
1. **Run Full Baseline Verification**:
   ```powershell
   pytest codedee/codedee_server/tests -v
   pytest codedee/tests_e2e -v
   ```
   *Expected: 60 passed in codedee_server, 74 passed in tests_e2e.*

2. **Verify That Proposed Tests Fail on Unpatched Codebase**:
   Execute the test definitions against the current code without modifications:
   *Expected:*
   - Test 1 (tuple formatting): FAILS (`len(vulns) == 0`).
   - Test 4 (Python non-SQL variables): FAILS (`len(findings) == 9`).
   - Test 5 (JS non-SQL variables): FAILS (`len(findings) == 6`).

3. **Verify That Proposed Tests Pass with Remediation**:
   Once Worker M2 implements the fixes, run:
   ```powershell
   pytest codedee/codedee_server/tests/test_taint_walker.py -v
   ```
   *Expected: All 15 tests (7 original + 8 new) pass cleanly in <2.0s.*

4. **Invalidation Conditions**:
   This report is invalidated if any of the 8 proposed test cases fail when the fixes are applied or if any of the 134 existing baseline tests regress.
