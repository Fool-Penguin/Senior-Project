# Handoff Report: Milestone 2 (R2 - Static Analysis & Graph Modeling Engine)

**Agent:** `worker_m2` (Agent 2: Static Analysis & Graph Engineer)  
**Parent / Recipient:** `cdd4c46b-fa83-40b4-992f-7161af706ca8` (orchestrator)  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\worker_m2`  
**Date:** 2026-11-01  
**Status:** 100% Complete & Independently Verified  

---

## 1. Observation

All assigned source files and test suites within Milestone 2 exclusive write ownership were implemented and tested:

### A. Source Implementation
1. `codedee/codedee_server/app/parser/cst_manager.py`:
   - Concrete Syntax Tree (CST) manager wrapping `tree-sitter` (v0.26.0), `tree-sitter-python` (v0.25.0), `tree-sitter-javascript` (v0.25.0), and `tree-sitter-typescript` (v0.23.2) supporting both `.ts` (`language_typescript()`) and `.tsx` (`language_tsx()`).
   - Strictly conforms to Tree-sitter 0.26 API by executing queries exclusively via `tree_sitter.QueryCursor(query).captures(node)` and `matches(node)`.
2. `codedee/codedee_server/app/graphs/call_graph.py`:
   - `CallGraphBuilder` generating `nx.DiGraph` representing intra-procedural and cross-file function calls.
   - Resolves Python `import module`, `from module import func`, relative imports, and JS/TS ES6 `import` / CommonJS `require()`.
   - Normalizes node identifiers with forward-slashed paths (`.replace('\\', '/')`) for cross-platform deterministic matching.
3. `codedee/codedee_server/app/graphs/cfg.py`:
   - `CFGBuilder` generating intra-procedural Control-Flow Graphs modeling branching statements (`if`, `elif`, `else`, `for`, `while`, `try`, `catch`/`except`, `finally`, `return`).
   - Connects execution transitions with typed edges: `FALLTHROUGH`, `TRUE_BRANCH`, `FALSE_BRANCH`, `LOOP_BODY`, `LOOP_EXIT`, `EXCEPTION_EDGE`, and `RETURN_EDGE`.
4. `codedee/codedee_server/app/graphs/dfg.py`:
   - `DFGBuilder` generating Data-Flow Graphs modeling Def-Use chains, string concatenations (`+`), interpolations (f-strings, template literals `${...}`), actual argument to formal parameter bindings, and return transfers.
   - Handles unwrapped `expression_statement` nodes in Tree-sitter CST to capture assignment definitions and updates.
   - Provides `link_inter_procedural_calls(call_graph)` to bind caller arguments to callee formal parameters across files.
5. `codedee/codedee_server/app/maintainability/engine.py`:
   - `MaintainabilityEngine` calculating EXACTLY 8 ISO/IEC 25010 metrics:
     - Function-level: (1) `cyclomatic_complexity` (McCabe CC), (2) `cognitive_complexity` (SonarQube specification), (3) `parameter_count`, (4) `function_sloc`.
     - File-level: (5) `file_sloc`, (6) `module_coupling` (Ce, Ca, instability), (7) `duplicated_blocks`, (8) `comment_density`.
     - Strictly and verifiably excludes forbidden metrics: SQALE, LCOM4, DIT, NOM, Raw LOC, and Nesting Depth.
6. `codedee/codedee_server/app/taint/walker.py`:
   - `SymbolicTaintWalker` performing graph reachability traversals on the DFG from untrusted input sources (`request.args`, `req.query`, `params`, etc.) to SQL execution sinks (`cursor.execute`, `db.query`, `client.query`, `connection.execute`, etc.).
   - Traces concatenations and format strings, detects parameterized query sanitization (`?`, `%s`, `$1`), and outputs structured findings strictly adhering to `SymbolicFinding` and `TaintPath`.

### B. Unit & Integration Test Suites
1. `codedee/codedee_server/tests/test_treesitter_graphs.py`:
   - 19 test cases covering multi-language CST parsing, syntax error detection, QueryCursor compatibility, Call Graph intra/inter-procedural linking, CFG branching, DFG def-use chains, f-strings, template literals, and cross-file argument binding.
   - Result: `19 passed in 0.65s`.
2. `codedee/codedee_server/tests/test_maintainability.py`:
   - 10 test cases verifying calculation of exactly the 8 ISO/IEC 25010 metrics and validating that prohibited metrics (SQALE, LCOM4, DIT, NOM, Raw LOC, Nesting Depth) are completely absent.
   - Result: `10 passed in 0.27s`.
3. `codedee/codedee_server/tests/test_taint_walker.py`:
   - 7 test cases verifying SQL injection taint path identification across Python, JavaScript, and TypeScript, including parameterized query recognition as safe, and cross-file taint path detection using real fixtures in `Security_CWE/cross_file_demo/`.
   - Result: `7 passed in 0.81s`.
4. Full Backend Test Suite:
   - Command: `python -m pytest codedee/codedee_server/tests`
   - Result: `60 passed in 17.47s` (100% pass rate).
5. Opaque-Box E2E Regression Test Suite:
   - Command: `python -m pytest -p no:anyio codedee/tests_e2e/`
   - Result: `74 passed, 2 warnings in 25.72s` (100% pass rate).

---

## 2. Logic Chain

1. **Tree-sitter 0.26 Compatibility**:
   - In `tree-sitter` 0.26.0, `Query.captures` raises an `AttributeError` because captures and matches were migrated to `QueryCursor`.
   - By creating `CSTParserManager` and routing every capture/match execution through `QueryCursor(query).captures(node)` / `.matches(node)`, zero breaking changes or runtime attribute errors occur across the engine.
2. **Path Normalization for Cross-File Linkage**:
   - On Windows, mixed separators (`\\` vs `/`) cause graph lookup misses between file imports and node registrations.
   - By consistently standardizing all internal node identifiers and module resolution targets using forward slashes (`.replace('\\', '/')`), cross-file references resolve reliably across platforms.
3. **CST Hierarchy Unwrapping in DFG**:
   - In modern Tree-sitter Python and JavaScript grammars, assignments (`x = y`) and augmented assignments (`x += y`) are wrapped inside `expression_statement`.
   - By unwrapping `expression_statement` to inspect its inner assignment node, `DFGBuilder` accurately captures every `ASSIGN_DEF` and preserves the Def-Use chain.
4. **Metric Integrity & Scope Compliance**:
   - Requirement R2 mandates computing strictly 8 ISO/IEC 25010 metrics while excluding SQALE, LCOM4, DIT, NOM, Raw LOC, and Nesting Depth.
   - McCabe CC counts base 1 + decision points; Cognitive Complexity enforces SonarQube's B1, B2 nesting penalties, and B3 boolean sequences; SLOC excludes comments and blanks; Coupling tracks Ce and Ca; Duplicated blocks detects identical statement subtree rolling hashes; Comment density measures comment ratio against total volume.
   - Prohibited metrics are excluded from both the computation logic and the Pydantic contracts.
5. **Symbolic Taint Traversal & Sanitization**:
   - Unvalidated strings concatenated via `+`, `%`, `.format()`, f-strings, or `${...}` that flow into SQL sink command arguments trigger `is_sanitized = False` with `severity = "CRITICAL"`.
   - When the SQL command is parameterized and untrusted data is supplied via parameter containers (tuples, lists), the engine flags `sanitized = True` with `severity = "LOW"`.
   - Cross-file call edges allow tracing taint from an HTTP controller into an imported storage service helper.

---

## 3. Caveats

1. **Dynamic Runtime Imports**: Dynamic import patterns such as `__import__(var)` or `eval(require(x))` cannot be resolved statically without symbolic execution. Standard ES6 `import`, CommonJS `require('./...')`, and Python `import` / `from ... import` statements are fully supported.
2. **Proprietary Query Builders**: The sink database catalog covers DB-API 2.0 (sqlite3, psycopg2, pymysql), SQLAlchemy, Django ORM, pg, mysql2, Prisma, and TypeORM. Custom in-house database wrappers should be added to `SINK_PATTERNS` if encountered in non-standard enterprise codebases.

---

## 4. Conclusion

Milestone 2 (R2 - Static Analysis & Graph Modeling Engine) is 100% complete and fully verified:
- `cst_manager.py` provides multi-language CST parsing with Tree-sitter 0.26 `QueryCursor` compliance.
- `call_graph.py`, `cfg.py`, and `dfg.py` construct rich NetworkX directed graphs modeling inter-procedural calls, branching decisions, and Def-Use value propagation.
- `engine.py` computes exactly the 8 authorized ISO/IEC 25010 metrics with zero forbidden metrics.
- `walker.py` performs symbolic taint propagation to SQL sinks, recognizing parameterized query sanitization.
- All 60 unit tests in `codedee_server/tests` and all 74 e2e tests in `codedee/tests_e2e` pass with 100% success.

---

## 5. Verification Method

To independently reproduce and verify all findings, execute:

1. **Run All Milestone 2 Unit Tests**:
   ```powershell
   python -m pytest codedee/codedee_server/tests/test_treesitter_graphs.py codedee/codedee_server/tests/test_maintainability.py codedee/codedee_server/tests/test_taint_walker.py -v
   ```
   *Expected result: 36 passed.*

2. **Run All Backend Tests (`codedee_server/tests`)**:
   ```powershell
   python -m pytest codedee/codedee_server/tests -v
   ```
   *Expected result: 60 passed.*

3. **Run End-to-End Test Suite**:
   ```powershell
   python -m pytest -p no:anyio codedee/tests_e2e/
   ```
   *Expected result: 74 passed.*
