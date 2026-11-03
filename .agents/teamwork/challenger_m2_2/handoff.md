# Adversarial Challenge Report: Milestone 2 (R2 - Static Analysis & Graph Modeling Engine)

**Agent:** `challenger_m2_2` (Adversarial Verifier & Empirical Challenger)  
**Parent / Recipient:** `cdd4c46b-fa83-40b4-992f-7161af706ca8` (orchestrator)  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\challenger_m2_2`  
**Date:** 2026-11-01  
**Verdict:** **REJECT** (Blocking issues discovered in `SymbolicTaintWalker` and `DFGBuilder`)

---

## 1. Observation

All 18 adversarial tests authored across two test suites (`test_adversarial_maintainability.py` and `test_adversarial_taint_walker.py`) were executed empirically via `pytest` in `d:\4th-year\Senior-Project`:

```powershell
pytest .agents/teamwork/challenger_m2_2/test_adversarial_maintainability.py .agents/teamwork/challenger_m2_2/test_adversarial_taint_walker.py -v
```
**Output:** `18 passed in 0.53s`.

### A. Maintainability Engine Observations (ISO/IEC 25010 Compliance)
1. **Forbidden Metrics Absence (`app/maintainability/engine.py:1-513` and `app/models/contracts.py:48-69`)**:
   - `MaintainabilityMetrics.model_fields` and `to_summary_dict()` expose strictly the 8 authorized metrics:
     `cyclomatic_complexity`, `cognitive_complexity`, `parameter_count`, `function_sloc`, `file_sloc`, `module_coupling`, `duplicated_blocks`, `comment_density`.
   - All forbidden metrics (`SQALE`, `sqale_rating`, `LCOM4`, `lcom`, `DIT`, `dit`, `NOM`, `nom`, `Raw LOC`, `raw_loc`, `Nesting Depth`, `nesting_depth`) are completely absent from schemas, engine methods, and output dictionaries.
2. **Edge Cases**:
   - Empty functions: Single-line (`def f(): pass`, `function f() {}`) accurately return `function_sloc == 1`, `CC == 1`, `Cog == 0`. Multi-line empty functions accurately return `function_sloc == 2`.
   - Huge single-line files: Minified scripts (>5,000 characters, 100 statements on a single line) evaluate without recursion errors or stack overflows (`file_sloc == 1`).
   - 100% comment files: Files with exclusively comments and whitespace evaluate cleanly without `ZeroDivisionError` (guaranteed by the SLOC floor `max(sloc, 1)` in `compute_file_sloc`).
   - Identical duplicated functions: Rolling statement subtree hashing detects repetitions across duplicate functions (`duplicated_blocks >= 1`).

### B. Symbolic Taint Walker & DFG Builder Observations (Critical Defect Findings)
1. **Defect 1: False Negative Evasion via Python `%` Tuple Formatting (`codedee/codedee_server/app/graphs/dfg.py:282-485`)**:
   - When user input is formatted via standard Python printf-style formatting with a tuple:
     ```python
     username = request.args.get("username")
     sql = "SELECT * FROM accounts WHERE name = '%s'" % (username,)
     cursor.execute(sql)
     ```
   - In `DFGBuilder._process_expression` (`dfg.py:282-485`), AST node type `tuple` (and `parenthesized_expression`) is unhandled and falls through to the generic literal branch (`node_kind="EXPRESSION"`), creating node `(username,)` **without visiting its child nodes**.
   - As a result, `username` inside `(username,)` is never connected to `sql`.
   - `SymbolicTaintWalker.analyze_code` returns **0 findings** (`len(findings) == 0`).
   - A textbook CWE-89 SQL injection completely evades static detection.
   - Verified empirically in `test_reproduce_bug_false_negative_tuple_formatting`.

2. **Defect 2: Severe False Positive Flood via Substring Sink Matching (`codedee/codedee_server/app/taint/walker.py:82-96`)**:
   - In `walker.py:82-96`:
     ```python
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
   - `SINK_PATTERNS` contains `"raw"` and `"query"`.
   - `if pattern in var_lower` performs a substring match against any variable name.
   - Consequently, **any variable containing `raw` or `query`** (e.g. `raw_text`, `raw_id`, `raw_data`, `search_query`, `user_query`, `drawing`) is classified as an **SQL execution sink**.
   - Code with **zero database interaction**:
     ```python
     def parse_raw(request):
         raw_text = request.args.get("text")
         return raw_text.strip()
     ```
     is flagged with **two CRITICAL CWE-89 SQL Injection findings**:
     `Source: request.args.get -> Sink: raw_text (Severity: CRITICAL)`
   - Verified empirically in `test_reproduce_bug_false_positive_substring_sink_matching`.

3. **Defect 3: False Positive in Fallback AST Scan on Variable Declarations (`codedee/codedee_server/app/taint/walker.py:328`)**:
   - In `_fallback_ast_sink_scan`:
     ```python
     is_sink = any(p in clean.lower() for p in self.SINK_PATTERNS)
     ```
   - If a constant template literal is assigned to a variable named `query`:
     ```javascript
     const query = `SELECT * FROM items WHERE approved = ${isApproved} LIMIT ${limit}`;
     db.query(query);
     ```
     the assignment line `const query = ...` itself matches `p in clean.lower()` (`"query"`), treating the variable declaration line as an SQL sink.
   - Because `${isApproved}` is interpolated on that line, it generates a CRITICAL SQL injection finding on safe, constant values.
   - Verified empirically in `test_reproduce_bug_false_positive_query_variable_name`.

---

## 2. Logic Chain

1. **Maintainability Engine is Verified Robust**:
   - Observations A.1 and A.2 demonstrate that `MaintainabilityEngine` meets all functional requirements and strict boundary constraints of Milestone 2 (R2).
   - Prohibited metrics are strictly blocked at schema and computational levels.
   - Edge cases (empty functions, massive single-line files, 100% comment files) evaluate deterministically.

2. **DFG Chain Disconnection Causes False Negatives**:
   - Observation B.1 proves that `DFGBuilder._process_expression` does not recurse into `tuple`, `parenthesized_expression`, or `list` AST nodes.
   - When arguments to formatting operators (`%`) or function calls are grouped in tuples, the Def-Use chain breaks.
   - Because the forward traversal from `request.args` terminates at the broken edge and cannot reach `cursor.execute`, and the AST fallback scan only inspects the sink invocation line (`cursor.execute(sql)` without formatting tokens on that line), the vulnerability is undetected.
   - This presents an unacceptable security blind spot where standard Python SQL formatting completely evades detection.

3. **Broad Substring Heuristic Triggers Massive False Positive Inundation**:
   - Observation B.2 proves that `pattern in var_lower` in `is_sink_node` matches substrings rather than exact database operations or invocation syntax.
   - In practical enterprise codebases, variable names like `raw_data`, `raw_id`, `raw_payload`, and `search_query` are ubiquitous.
   - Classifying non-sink assignments as SQL sinks produces false positives that destroy SAST credibility and will corrupt downstream Stage 3B Neuro-Symbolic evaluations and Multi-Gate verification.

4. **Verdict Justification**:
   - While the Maintainability Engine passes, the Static Analysis & Graph Modeling Engine (Milestone 2) is incomplete and compromised by Defect 1 (False Negatives) and Defect 2 (False Positives).
   - Per the Empirical Challenger protocol, critical flaws that compromise engine integrity require **REJECT** until remediated.

---

## 3. Caveats

1. **AST Fallback Dependency**: The presence of `_fallback_ast_sink_scan` in `SymbolicTaintWalker` masks underlying DFG disconnection bugs in test suites that rely on single-line sink statements.
2. **Dynamic Query Construction**: Advanced SQL construction patterns (e.g. dynamic dictionary unpacking or custom string builder classes) were not tested in this milestone and remain out of scope for CWE-89 vertical slice.

---

## 4. Conclusion

**Verdict: REJECT**

Milestone 2 is rejected due to two high-severity defects in `SymbolicTaintWalker` and `DFGBuilder`:
1. **Critical False Negative**: `DFGBuilder` drops `tuple` AST nodes, allowing `% (user_input,)` SQL injections to evade detection with zero findings.
2. **Critical False Positive**: `SymbolicTaintWalker.is_sink_node` performs substring matching on `var_name` for `'raw'` and `'query'`, flagging safe non-SQL code (e.g. `raw_text = request.args.get('text')`) as CRITICAL CWE-89 SQL injections.

### Required Actionable Remediations for Worker M2:
1. **Fix `dfg.py:282` (`_process_expression`)**:
   Add explicit handling for `tuple`, `parenthesized_expression`, and `list` AST nodes to recursively process and connect all nested child identifier expressions into the DFG.
2. **Fix `walker.py:82` (`is_sink_node`)**:
   Remove loose substring matching `if pattern in var_lower: return True`. Require either:
   - Specific method call prefixes: `f".{pattern}(" in expr_lower` or `f"{pattern}(" in expr_lower`, OR
   - Exact matching on qualified database objects/methods (`cursor.execute`, `db.query`, `client.query`), avoiding generic words like `"raw"` and `"query"` matching variable names.
3. **Fix `walker.py:328` (`_fallback_ast_sink_scan`)**:
   Ensure fallback scan excludes variable assignment statements (`const `, `let `, `var `, `= `) from being misidentified as sink invocation lines.

---

## 5. Verification Method

To independently reproduce all adversarial findings and verify the defect proofs:

1. **Run Full Challenger Test Suite (18 tests)**:
   ```powershell
   pytest .agents/teamwork/challenger_m2_2/test_adversarial_maintainability.py .agents/teamwork/challenger_m2_2/test_adversarial_taint_walker.py -v
   ```
   *Expected result: 18 passed in <1.0s (including 3 explicit defect reproduction proofs).*

2. **Run Individual Defect Reproductions**:
   ```powershell
   # Defect 1: False negative evasion on % (tuple,)
   pytest .agents/teamwork/challenger_m2_2/test_adversarial_taint_walker.py -k "test_reproduce_bug_false_negative_tuple_formatting" -v

   # Defect 2: False positive on non-SQL raw_text variable
   pytest .agents/teamwork/challenger_m2_2/test_adversarial_taint_walker.py -k "test_reproduce_bug_false_positive_substring_sink_matching" -v

   # Defect 3: False positive on const query = ... template literal
   pytest .agents/teamwork/challenger_m2_2/test_adversarial_taint_walker.py -k "test_reproduce_bug_false_positive_query_variable_name" -v
   ```

3. **Invalidation Condition**:
   This rejection is invalidated once Worker M2 updates `dfg.py` and `walker.py` such that `test_evasion_percent_tuple_python` detects the SQL injection while `test_fp_constant_numeric_boolean_javascript_template` and non-SQL variables with `raw_*` / `*query*` report zero false positives.
