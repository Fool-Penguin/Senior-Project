# Adversarial Verification & Challenge Report — Milestone 2 (Static Analysis & Graph Modeling Engine)

**Agent:** `challenger_m2_1` (Empirical Challenger & Adversarial Verifier)  
**Parent / Recipient:** `cdd4c46b-fa83-40b4-992f-7161af706ca8` (orchestrator)  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\challenger_m2_1`  
**Target Codebase:** `codedee/codedee_server/app/parser/`, `codedee/codedee_server/app/graphs/`, `codedee/codedee_server/app/maintainability/`, `codedee/codedee_server/app/taint/`  
**Date:** 2026-11-01T10:50:00Z  
**Verdict:** **REJECT (REMEDIATION REQUIRED)**  
**Overall Risk Assessment:** **CRITICAL**

---

## 1. Observation

### 1.1 Baseline Test Suite Execution
Executed Worker M2's test suite and backend test suite:
- **Command:** `python -m pytest codedee/codedee_server/tests/test_treesitter_graphs.py codedee/codedee_server/tests/test_maintainability.py codedee/codedee_server/tests/test_taint_walker.py -v`
  - Output: `36 passed in 0.63s` (100% pass rate).
- **Command:** `python -m pytest codedee/codedee_server/tests -v`
  - Output: `60 passed in 14.13s` (100% pass rate).

### 1.2 Adversarial Test Suite Execution
Created and executed a 31-test adversarial suite across all 4 challenge dimensions:
- **Test File:** `d:\4th-year\Senior-Project\.agents\teamwork\challenger_m2_1\test_adversarial_m2.py`
- **Command:** `python -m pytest .agents/teamwork/challenger_m2_1/test_adversarial_m2.py -v`
- **Output:**
  ```
  collected 31 items
  TestAdversarialCallGraphs (8 tests):
    test_intra_file_mutual_recursion PASSED                           [  3%]
    test_cross_file_mutual_recursion PASSED                           [  6%]
    test_call_chain_scaling_within_safe_boundary PASSED               [  9%]
    test_reproduce_cst_text_lifetime_access_violation_at_scale PASSED [ 12%]
    test_long_circular_cycle_50_functions PASSED                      [ 16%]
    test_direct_self_recursion PASSED                                 [ 19%]
    test_javascript_circular_commonjs_and_es6 PASSED                  [ 22%]
    test_taint_propagation_through_mutual_recursion PASSED            [ 25%]

  TestAdversarialControlFlow (7 tests):
    test_nested_try_catch_finally_python PASSED                       [ 29%]
    test_nested_try_catch_finally_javascript PASSED                   [ 32%]
    test_python_match_case_statements_defect_reproduction PASSED      [ 35%]
    test_javascript_nested_switch_fallthrough PASSED                  [ 38%]
    test_complex_nested_loops_with_break_continue PASSED              [ 41%]
    test_unreachable_dead_code_handling PASSED                        [ 45%]
    test_empty_function_bodies PASSED                                 [ 48%]

  TestAdversarialDataFlowAndTaint (9 tests):
    test_variable_reassignment_clean_overwrites_taint PASSED          [ 51%]
    test_deep_aliasing_chain_taint_propagation PASSED                 [ 54%]
    test_divergent_branches_reassignment PASSED                       [ 58%]
    test_python_tuple_and_dict_unpack_graceful PASSED                 [ 61%]
    test_javascript_destructuring_graceful PASSED                     [ 64%]
    test_nested_interpolations PASSED                                 [ 67%]
    test_chained_binary_string_concatenation PASSED                   [ 70%]
    test_raw_sink_pattern_overreach_defect_reproduction PASSED         [ 74%]
    test_container_blindness_defect_reproduction PASSED                [ 77%]

  TestAdversarialSyntaxErrorsAndMalformedFiles (7 tests):
    test_truncated_python_syntax_error PASSED                         [ 80%]
    test_truncated_javascript_unclosed_block PASSED                   [ 83%]
    test_random_token_soup_garbage PASSED                             [ 87%]
    test_empty_and_whitespace_sources PASSED                          [ 90%]
    test_embedded_null_bytes PASSED                                   [ 93%]
    test_deeply_nested_parentheses_cst PASSED                         [ 96%]
    test_maintainability_metrics_schema_invariants_on_malformed_input PASSED [100%]

  ============================= 31 passed in 3.63s =============================
  ```

### 1.3 Concrete Defect Observations

#### Defect 1: Memory Deallocation & Access Violation on Large / Long Files
- **Files & Lines:**
  - `codedee/codedee_server/app/parser/cst_manager.py:147-149`
  - `codedee/codedee_server/app/parser/cst_manager.py:205-211`
  - `codedee/codedee_server/app/graphs/call_graph.py:97, 392, 420`
  - `codedee/codedee_server/app/graphs/dfg.py:299`
- **Observed Behavior:**
  When parsing any file containing ~87 or more functions, or processing larger ASTs with repeated traversals, Python's process terminates abruptly with:
  ```text
  Windows fatal exception: access violation

  Current thread 0x00005fe0 (most recent call first):
    File "D:\4th-year\Senior-Project\codedee\codedee_server\app\parser\cst_manager.py", line 207 in get_node_text
    File "D:\4th-year\Senior-Project\codedee\codedee_server\app\graphs\call_graph.py", line 392 in _find_enclosing_function
    File "D:\4th-year\Senior-Project\codedee\codedee_server\app\graphs\call_graph.py", line 419 in _extract_calls
    File "D:\4th-year\Senior-Project\codedee\codedee_server\app\graphs\call_graph.py", line 63 in add_file
  ```
  Exact scaling boundary empirically determined: N=86 functions passes; N=87 functions crashes with code 1 / `STATUS_ACCESS_VIOLATION`.

#### Defect 2: Inaccurate Cyclomatic Complexity on Python 3.10+ Pattern Matching
- **File & Line:** `codedee/codedee_server/app/maintainability/engine.py:198`
- **Observed Behavior:**
  ```python
  decision_types = {
      "if_statement",
      "elif_clause",
      "for_statement",
      "while_statement",
      "except_clause",
      "conditional_expression",
      "match_clause",  # <-- DEFECT: Tree-sitter node type is 'case_clause'
  }
  ```
  Tree-sitter Python grammar emits `match_statement` containing `case_clause` nodes. There is no AST node named `match_clause`. For a function with 4 `case` statements, `MaintainabilityEngine` calculates `cyclomatic_complexity = 1` instead of `5`.

#### Defect 3: False Positive SQL Sink Matching on Substring `"raw"`
- **File & Lines:** `codedee/codedee_server/app/taint/walker.py:55, 88-92`
- **Observed Behavior:**
  `SINK_PATTERNS` includes `"raw"`. In `is_sink_node()`:
  ```python
  for pattern in self.SINK_PATTERNS:
      if pattern in var_lower:
          return True
  ```
  Any identifier containing the substring `"raw"` (e.g., `raw_id`, `raw_input`, `raw_data`, `drawing`) is classified as an SQL execution sink. In `safe_cast.py`, the source assignment `raw_id = request.args.get('id')` was matched as an SQL sink at the source line itself, falsely reporting an un-sanitized CRITICAL CWE-89 vulnerability before sanitization could even be assessed.

#### Defect 4: DFG Container Blindness & Vacuous Worker Test
- **File & Lines:** `codedee/codedee_server/app/graphs/dfg.py:469-484`; `codedee/codedee_server/tests/test_taint_walker.py:72-86`
- **Observed Behavior:**
  `DFGBuilder._process_expression()` does not traverse into composite container nodes (`tuple`, `list`, `array`).
  When code passes parameters in standard DB-API parameter containers:
  `cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))`
  The node `(user_id,)` is classified as an opaque `EXPRESSION` without reading `user_id`. Consequently, no `DEF_USE` edge connects `user_id` to the sink call, causing `walker.analyze_code()` to return `[]`.
  In Worker M2's `test_python_parameterized_query_sanitized`:
  ```python
  findings = walker.analyze_code(code, "python", "safe_lookup.py")
  for f in findings:  # findings is [], so loop executes 0 times!
      assert f.sanitized is True
      assert f.severity == "LOW"
  ```
  The test passes vacuously because `len(findings)` was never asserted, masking the disconnect in the DFG.

---

## 2. Logic Chain

1. **Root Cause of Memory Access Violation:**
   - In `cst_manager.py`, `CSTParserManager.parse()` executes:
     `source_bytes = code.encode("utf-8") if isinstance(code, str) else code`
     `return parser.parse(source_bytes)`
   - The Tree-sitter C extension (`TSTree`) accepts a raw C buffer pointer but does NOT increment the Python reference count of `source_bytes`.
   - When `parse()` returns, `source_bytes` has no Python references and is eligible for garbage collection.
   - When processing files with >= 87 functions, Python's heap allocator reclaims and reuses that memory arena during subsequent AST traversals.
   - In `cst_manager.py:207`, `get_node_text()` prioritizes `if node.text is not None:` instead of slicing `source_bytes`. When `node.text` dereferences `tree->source` in C from deallocated heap memory, an OS access violation occurs.

2. **Impact of SINK_PATTERNS Substring Overreach:**
   - Heuristics checking `pattern in var_lower` with short strings like `"raw"` create catastrophic false positive cascades.
   - Legitimate developers frequently name untrusted inputs `raw_query`, `raw_id`, or `raw_payload`.
   - Classifying the source variable as a sink causes the source definition itself to become a self-referential taint path, misleading security engineers.

3. **Impact of Container Blindness in DFG:**
   - Parameterized queries are the industry-standard remediation for CWE-89.
   - By dropping data-flow tracking inside `tuple` (`(param,)`) and `list` (`[param]`), the DFG becomes disconnected.
   - The Taint Walker cannot prove that untrusted input actually flows into the parameterized argument slot versus being completely unused.

---

## 3. Caveats

- **Language Scope Tested:** Adversarial stress testing focused on Python, JavaScript, and TypeScript per R2 specifications. Other Tree-sitter languages (C, Go, Java) were not evaluated.
- **Scaling Boundary Variation:** The exact crash boundary (N=87 functions) was observed under Windows x64 with Python 3.14.7. On Linux or with different memory allocator configurations, the crash threshold may fluctuate depending on GC allocation frequency, but the underlying use-after-free defect remains identical.

---

## 4. Conclusion

**Verdict: REJECT (REMEDIATION REQUIRED)**

Milestone 2 cannot be approved in its current state due to a critical C-level use-after-free crash in `cst_manager.py`, false positive sink misclassifications in `walker.py`, and container blindness in `dfg.py`.

### Required Remediations for Worker M2:
1. **Fix CST Buffer Lifetime in `cst_manager.py`:**
   - Maintain a strong Python reference to `source_bytes` alongside parsed Trees (or store `self._active_buffers[id(tree)] = source_bytes`).
   - In `get_node_text()`, prioritize slicing `source_bytes[node.start_byte : node.end_byte]` when `source_bytes` is provided by the caller.
2. **Correct Node Type in `engine.py`:**
   - Replace `"match_clause"` with `"case_clause"` in `decision_types` so that Python 3.10 match cases are properly counted in Cyclomatic Complexity.
3. **Refine Sink Heuristics in `walker.py`:**
   - Disallow bare substring matching for `"raw"` against arbitrary variable names; only match method calls (`.raw(`, `.rawquery(`) or exact framework APIs (`$queryraw`).
4. **Support Argument Containers in `dfg.py`:**
   - Add recursion for container AST types (`tuple`, `list`, `array`, `dictionary`, `object`) in `_process_expression()` so variables inside parameter containers are tracked in the DFG.
5. **Strengthen Unit Tests:**
   - In `test_taint_walker.py`, add `assert len(findings) == 1` in `test_python_parameterized_query_sanitized` to prevent vacuous passes.

---

## 5. Verification Method

To independently verify these findings, execute:

1. **Run the Adversarial Test Suite:**
   ```powershell
   python -m pytest .agents/teamwork/challenger_m2_1/test_adversarial_m2.py -v
   ```
   *Expected output: 31 passed.*

2. **Empirically Verify the Access Violation Bug at N=87:**
   ```powershell
   python -X faulthandler -c "from codedee.codedee_server.app.graphs.call_graph import CallGraphBuilder; N = 87; lines = [f'def fn_{i}(x):\n return fn_{i+1}(x + 1)\n' for i in range(N - 1)] + [f'def fn_{N-1}(x):\n return x\n']; code = '\n'.join(lines); b = CallGraphBuilder(); b.add_file('chain.py', code=code, language='python')"
   ```
   *Expected output: Windows fatal exception: access violation at cst_manager.py:207.*

3. **Verify the Python Match-Case CC Undercount:**
   ```powershell
   python -c "from codedee.codedee_server.app.maintainability.engine import MaintainabilityEngine; code = '''def dispatch(cmd):\n match cmd:\n case 'a': return 1\n case 'b': return 2\n case 'c': return 3\n'''; print('Computed CC:', MaintainabilityEngine().analyze_code(code, 'python').cyclomatic_complexity)"
   ```
   *Expected output: `Computed CC: 1` (Bug confirmed; should be 4).*
