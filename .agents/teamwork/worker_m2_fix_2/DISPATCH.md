## 2026-11-01T11:15:00Z
You are worker_m2_fix_2, a software engineering worker for CodeDEE.
Your working directory is: d:\4th-year\Senior-Project\.agents\teamwork\worker_m2_fix_2
You MUST read the original request file first: d:\4th-year\Senior-Project\.agents\teamwork\ORIGINAL_REQUEST.md
Also read the project architecture document: d:\4th-year\Senior-Project\.agents\teamwork\orchestrator\PROJECT.md
Also read the technical fix reports and specifications:
- d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_fix_1\handoff.md
- d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_fix_1\dfg_tuple_fix.patch
- d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_fix_2\handoff.md
- d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_fix_3\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Assigned Scope: Milestone 2 Iteration 2 Remediation
Exclusive Write Ownership:
- d:\4th-year\Senior-Project\codedee\codedee_server\app\graphs\dfg.py
- d:\4th-year\Senior-Project\codedee\codedee_server\app\taint\walker.py
- d:\4th-year\Senior-Project\codedee\codedee_server\tests\test_taint_walker.py

Key Tasks:
1. In `app/graphs/dfg.py`:
   - In `_process_expression`: recursively process collection and grouping AST nodes:
     - `parenthesized_expression`: unwrap inner expression.
     - `tuple`, `list`, `array`, `set`, `sequence_expression`: create COLLECTION node, recursively evaluate all child elements, link `elem_id -> coll_id`, and return `[coll_id]`.
     - `dictionary`, `object`, `pair`: recursively evaluate values and connect.
     - `await_expression`: unwrap inner call expression so `await client.query(...)` correctly generates CALL_ARG edges.
   Refer to `explorer_m2_fix_1/dfg_tuple_fix.patch` and `explorer_m2_fix_2/handoff.md` for exact CST node handling.

2. In `app/taint/walker.py`:
   - In `is_sink_node`: eliminate loose substring checks `pattern in var_lower` that caused variables containing "raw" or "query" (e.g. `raw_text = req.args.get('text')` or `search_query = req.args.get('q')`) to be falsely flagged as SQL sinks. Sinks must strictly be function/method calls on database interfaces (`.execute(`, `.query(`, `.raw(`, etc.) or exact recognized sink identifiers when `node_kind == "CALL_ARG"`.
   - In `is_sink_parameterized`: distinguish JS callback functions `(err, rows) =>` from parameter containers.
   - In `_fallback_ast_sink_scan`: filter out plain variable declarations (`const `, `let `, `var `) from being treated as sinks.
   Refer to `explorer_m2_fix_2/handoff.md` for exact line-by-line diff and rules.

3. In `tests/test_taint_walker.py`:
   - Add tests verifying Python `%` tuple formatting (`sql = "SELECT * FROM users WHERE name = '%s'" % (user_input,)`) is flagged as CRITICAL CWE-89.
   - Add tests verifying variables with "query" or "raw" in their names without database calls are NOT flagged (no false positives).
   - Add tests verifying JS template literals with non-SQL variables are NOT flagged.
   Refer to `explorer_m2_fix_3/handoff.md` for the test cases.

4. Run tests:
   - Run `pytest codedee\codedee_server\tests -v` (all unit tests must pass).
   - Run `python -m pytest -p no:anyio codedee/tests_e2e/` (all 74 E2E tests must pass).

5. Document all changes, files touched, test outputs, and verification methods in:
   `d:\4th-year\Senior-Project\.agents\teamwork\worker_m2_fix_2\handoff.md`.

6. Send a message to your parent orchestrator when complete.
